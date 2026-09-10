import pytest
from db_utils import build_dynamic_update_query


def test_build_dynamic_update_query_basic():
    query, params = build_dynamic_update_query(
        table_name="companies",
        update_fields={"status": "active", "updated_at": "NOW()"},
        where_clause="id = :cid",
        where_params={"cid": "test-uuid"},
    )
    assert "UPDATE companies SET" in query
    assert "status = :u_status" in query
    assert "updated_at = NOW()" in query
    assert "WHERE id = :cid" in query
    assert params["u_status"] == "active"
    assert params["cid"] == "test-uuid"


def test_build_dynamic_update_query_empty_error():
    with pytest.raises(ValueError, match="update_fields must not be empty"):
        build_dynamic_update_query("companies", {}, "id = :cid")


def test_build_dynamic_update_query_invalid_column():
    with pytest.raises(ValueError, match="Invalid column name"):
        build_dynamic_update_query("companies", {"bad;col": "val"}, "id = :cid")
