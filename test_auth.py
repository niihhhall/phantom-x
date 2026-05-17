import uuid
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import api_app
import app.core.database

# Setup Mock Supabase Client matching exact Postgrest Builder pattern
class MockExecuteResult:
    def __init__(self, data):
        self.data = data

class MockTable:
    def __init__(self, name, db_state):
        self.name = name
        self.db_state = db_state
        self.filters = {}
        self.pending_action = None

    def select(self, *args, **kwargs):
        return self

    def eq(self, column, value):
        self.filters[column] = value
        return self

    def insert(self, data):
        self.pending_action = ("insert", data)
        return self

    def update(self, data):
        self.pending_action = ("update", data)
        return self

    def delete(self):
        self.pending_action = ("delete", None)
        return self

    async def execute(self):
        if self.pending_action:
            action, data = self.pending_action
            self.pending_action = None # reset
            
            if action == "insert":
                if isinstance(data, list):
                    inserted = []
                    for item in data:
                        item_copy = item.copy()
                        if "id" not in item_copy:
                            item_copy["id"] = str(uuid.uuid4())
                        self.db_state[self.name].append(item_copy)
                        inserted.append(item_copy)
                    return MockExecuteResult(inserted)
                else:
                    data_copy = data.copy()
                    if "id" not in data_copy:
                        data_copy["id"] = str(uuid.uuid4())
                    self.db_state[self.name].append(data_copy)
                    return MockExecuteResult([data_copy])
                    
            elif action == "update":
                updated = []
                for item in self.db_state[self.name]:
                    match = True
                    for col, val in self.filters.items():
                        if item.get(col) != val:
                            match = False
                            break
                    if match:
                        item.update(data)
                        updated.append(item)
                return MockExecuteResult(updated)
                
            elif action == "delete":
                remaining = []
                deleted = []
                for item in self.db_state[self.name]:
                    match = True
                    for col, val in self.filters.items():
                        if item.get(col) != val:
                            match = False
                            break
                    if match:
                        deleted.append(item)
                    else:
                        remaining.append(item)
                self.db_state[self.name] = remaining
                return MockExecuteResult(deleted)
                
        # Default fallback to select query
        results = []
        for item in self.db_state[self.name]:
            match = True
            for col, val in self.filters.items():
                if item.get(col) != val:
                    match = False
                    break
            if match:
                results.append(item)
        return MockExecuteResult(results)

class MockSupabaseClient:
    def __init__(self):
        self.db_state = {
            "workspaces": [],
            "users": [],
            "linkedin_accounts": [],
            "leads": [],
            "campaigns": [],
            "messages": [],
            "jobs": []
        }

    def table(self, table_name):
        return MockTable(table_name, self.db_state)

mock_db = MockSupabaseClient()
app.core.database.get_db_client = lambda: mock_db

import app.api.routes.auth
import app.core.auth
app.api.routes.auth.get_db_client = lambda: mock_db
app.core.auth.get_db_client = lambda: mock_db

async def test_auth_flow():
    async with AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test") as client:
        print("\n--- Starting Auth System Integration Tests ---")
        
        # 1. Register User & Workspace
        print("Testing registration: POST /auth/register...")
        reg_payload = {
            "email": "test@phantom-x.ai",
            "password": "SecurePassword123!",
            "workspace_name": "Antigravity Inc"
        }
        res_reg = await client.post("/auth/register", json=reg_payload)
        assert res_reg.status_code == 201, f"Registration failed: {res_reg.text}"
        reg_data = res_reg.json()
        assert "access_token" in reg_data
        assert reg_data["user"]["email"] == "test@phantom-x.ai"
        assert reg_data["user"]["role"] == "owner"
        print("Registration successful!")

        # 2. Test Register Duplicate Email (should fail)
        print("Testing duplicate registration prevention...")
        res_dup = await client.post("/auth/register", json=reg_payload)
        assert res_dup.status_code == 400, "Duplicate registration allowed!"
        print("Duplicate registration correctly rejected.")

        # 3. Login
        print("Testing login: POST /auth/login...")
        login_payload = {
            "email": "test@phantom-x.ai",
            "password": "SecurePassword123!"
        }
        res_login = await client.post("/auth/login", json=login_payload)
        assert res_login.status_code == 200, f"Login failed: {res_login.text}"
        login_data = res_login.json()
        assert "access_token" in login_data
        token = login_data["access_token"]
        print("Login successful!")

        # 4. Test Login with Incorrect Password (should fail)
        print("Testing login failure with wrong password...")
        res_wrong = await client.post("/auth/login", json={
            "email": "test@phantom-x.ai",
            "password": "WrongPassword"
        })
        assert res_wrong.status_code == 401, "Allowed login with incorrect credentials!"
        print("Login with incorrect password correctly rejected.")

        # 5. Access Protected Endpoint /me
        print("Testing protected route access: GET /auth/me...")
        headers = {"Authorization": f"Bearer {token}"}
        res_me = await client.get("/auth/me", headers=headers)
        assert res_me.status_code == 200, f"Me endpoint failed: {res_me.text}"
        me_data = res_me.json()
        assert me_data["email"] == "test@phantom-x.ai"
        assert me_data["role"] == "owner"
        print("Protected route accessed successfully!")

        print("\n[SUCCESS] AUTH OK")

if __name__ == "__main__":
    try:
        asyncio.run(test_auth_flow())
    except AssertionError as e:
        print(f"\n[FAILURE] Auth Test Failed: {e}")
        exit(1)
