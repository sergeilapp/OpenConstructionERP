from app.modules.field_time.models import FieldTimesheetLine


def test_field_time_line_omits_mixed_external_create_all_fks() -> None:
    foreign_key_columns = {fk.parent.name for fk in FieldTimesheetLine.__table__.foreign_keys}

    assert "timesheet_id" in foreign_key_columns
    assert "resource_id" not in foreign_key_columns
    assert "equipment_id" not in foreign_key_columns
    assert "variation_id" not in foreign_key_columns
