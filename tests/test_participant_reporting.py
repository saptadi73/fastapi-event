import csv
import io

from app.modules.participants.reporting import ParticipantReportingService


def test_participant_csv_keeps_multiple_packages_as_separate_rows():
    rows = [{
        "participant_id": "participant-1",
        "full_name": "Participant One",
        "email": "one@example.com",
        "phone": None,
        "country": "Indonesia",
        "organization_name": "Example Org",
        "packages": [
            {"package_code": "A", "package_name": "Package A", "payment_status": "success"},
            {"package_code": "C", "package_name": "Package C", "payment_status": "pending"},
        ],
    }]

    exported = list(csv.DictReader(io.StringIO(ParticipantReportingService.csv(rows))))

    assert len(exported) == 2
    assert [row["package_code"] for row in exported] == ["A", "C"]
    assert [row["payment_status"] for row in exported] == ["success", "pending"]
    assert all(row["participant_id"] == "participant-1" for row in exported)
