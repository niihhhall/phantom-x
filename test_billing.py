# test_billing.py
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi import HTTPException
import pytest

from app.core.billing import (
    get_workspace_quota_limits,
    verify_linkedin_account_quota,
    verify_outreach_rotation_quota,
    verify_email_enrichment_quota,
    verify_leads_quota
)

# Mock data
WORKSPACE_ID = "e132924a-0202-4c33-9a23-9c67674d4cfb"

@pytest.mark.asyncio
async def test_get_workspace_quota_limits_success():
    """Verify that get_workspace_quota_limits correctly retrieves limits via RPC execution."""
    mock_res = MagicMock()
    mock_res.data = {
        "max_linkedin_accounts": 5,
        "max_daily_actions_per_account": 100,
        "max_leads_per_month": 2000,
        "allow_ai_personalization": True,
        "allow_email_enrichment": True,
        "allow_multi_account_rotation": True
    }
    
    mock_rpc = MagicMock()
    mock_rpc.execute = AsyncMock(return_value=mock_res)
    
    mock_db = MagicMock()
    mock_db.rpc.return_value = mock_rpc
    
    with patch("app.core.billing.get_db_client", return_value=mock_db):
        limits = await get_workspace_quota_limits(WORKSPACE_ID)
        assert limits["max_linkedin_accounts"] == 5
        assert limits["max_leads_per_month"] == 2000
        assert limits["allow_multi_account_rotation"] is True

@pytest.mark.asyncio
async def test_verify_linkedin_account_quota_breach():
    """Assert verify_linkedin_account_quota throws 403 Forbidden on exceeding allowed accounts limit."""
    mock_limits = {
        "max_linkedin_accounts": 1
    }
    
    mock_res = MagicMock()
    mock_res.count = 2  # Exceeds limit of 1
    
    mock_chain = MagicMock()
    mock_chain.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_res)
    
    mock_db = MagicMock()
    mock_db.table.return_value = mock_chain
    
    with patch("app.core.billing.get_workspace_quota_limits", return_value=mock_limits), \
         patch("app.core.billing.get_db_client", return_value=mock_db):
        
        with pytest.raises(HTTPException) as exc_info:
            await verify_linkedin_account_quota(WORKSPACE_ID)
            
        assert exc_info.value.status_code == 403
        assert "maximum limit" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_outreach_rotation_quota_breach():
    """Assert verify_outreach_rotation_quota throws 403 when trying to rotate on Starter tier."""
    mock_limits = {
        "allow_multi_account_rotation": False
    }
    
    with patch("app.core.billing.get_workspace_quota_limits", return_value=mock_limits):
        with pytest.raises(HTTPException) as exc_info:
            # Passing list of 2 account IDs to rotate
            await verify_outreach_rotation_quota(WORKSPACE_ID, ["acct_1", "acct_2"])
            
        assert exc_info.value.status_code == 403
        assert "restricted to Pro and Agency tiers" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_email_enrichment_quota_breach():
    """Assert verify_email_enrichment_quota blocks non-paid enrichment attempts."""
    mock_limits = {
        "allow_email_enrichment": False
    }
    
    with patch("app.core.billing.get_workspace_quota_limits", return_value=mock_limits):
        with pytest.raises(HTTPException) as exc_info:
            await verify_email_enrichment_quota(WORKSPACE_ID)
            
        assert exc_info.value.status_code == 403
        assert "only available on paid plans" in exc_info.value.detail

@pytest.mark.asyncio
async def test_verify_leads_quota_breach():
    """Assert verify_leads_quota blocks scrape/imports exceeding plan scope."""
    mock_limits = {
        "max_leads_per_month": 500
    }
    
    mock_res = MagicMock()
    mock_res.count = 499
    
    mock_chain = MagicMock()
    mock_chain.select.return_value.eq.return_value.execute = AsyncMock(return_value=mock_res)
    
    mock_db = MagicMock()
    mock_db.table.return_value = mock_chain
    
    with patch("app.core.billing.get_workspace_quota_limits", return_value=mock_limits), \
         patch("app.core.billing.get_db_client", return_value=mock_db):
        
        with pytest.raises(HTTPException) as exc_info:
            # Trying to import 10 new leads (499 + 10 = 509, breaching 500 cap)
            await verify_leads_quota(WORKSPACE_ID, new_import_count=10)
            
        assert exc_info.value.status_code == 403
        assert "exceed your workspace monthly lead capacity" in exc_info.value.detail

if __name__ == "__main__":
    # Execute the test cases sequentially for visual validation
    print("Running Billing Quota Test Suite...\n")
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(test_get_workspace_quota_limits_success())
        print("test_get_workspace_quota_limits_success: PASSED")
        
        loop.run_until_complete(test_verify_linkedin_account_quota_breach())
        print("test_verify_linkedin_account_quota_breach: PASSED")
        
        loop.run_until_complete(test_verify_outreach_rotation_quota_breach())
        print("test_verify_outreach_rotation_quota_breach: PASSED")
        
        loop.run_until_complete(test_verify_email_enrichment_quota_breach())
        print("test_verify_email_enrichment_quota_breach: PASSED")
        
        loop.run_until_complete(test_verify_leads_quota_breach())
        print("test_verify_leads_quota_breach: PASSED")
        
        print("\nALL BILLING QUOTA TESTS PASSED SUCCESSFULLY!")
    except AssertionError as ae:
        print(f"Assertion failed: {ae}")
    except Exception as e:
        print(f"Test execution failed with error: {e}")
