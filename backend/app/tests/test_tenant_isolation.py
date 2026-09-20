import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.hospital import Hospital
from app.db.models.auth import User, HospitalStaff
from app.db.models.doctor import Doctor
from app.db.models.enums import HospitalStatus, UserRole, DoctorStatus
from app.core.security import get_password_hash


@pytest.mark.asyncio
async def test_tenant_isolation_hospital_admin_cannot_modify_other_hospital(
    client: AsyncClient,
    db_session: AsyncSession,
    make_auth_headers,
):
    # Create Hospital A and Hospital B
    hosp_a = Hospital(name="Hospital Alpha", slug="hosp-a", address="1st Ave", phone="111", email="a@a.com", status=HospitalStatus.APPROVED)
    hosp_b = Hospital(name="Hospital Beta", slug="hosp-b", address="2nd Ave", phone="222", email="b@b.com", status=HospitalStatus.APPROVED)
    db_session.add_all([hosp_a, hosp_b])
    await db_session.flush()

    # User A is Hospital Admin for Hospital A
    user_a = User(email="admin.a@hosp.com", hashed_password=get_password_hash("pass"), full_name="Admin A", role=UserRole.HOSPITAL_ADMIN)
    db_session.add(user_a)
    await db_session.flush()

    staff_a = HospitalStaff(user_id=user_a.id, hospital_id=hosp_a.id)
    db_session.add(staff_a)
    await db_session.flush()

    headers_a = make_auth_headers(user_id=user_a.id, role=UserRole.HOSPITAL_ADMIN.value, hospital_id=hosp_a.id)

    # 1. Admin A tries to modify Hospital B configuration -> Forbidden (403)
    res = await client.put(
        f"/api/hospitals/{hosp_b.id}",
        json={"name": "Hacked Beta Hospital"},
        headers=headers_a,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "TENANT_ACCESS_DENIED"

    # 2. Admin A tries to add a doctor into Hospital B -> Forbidden (403)
    doc_payload = {
        "name": "Dr. Rogue",
        "hospital_id": hosp_b.id,
        "qualifications": "MD",
        "experience_years": 5,
        "appointment_duration_minutes": 30,
    }
    res_doc = await client.post("/api/doctors", json=doc_payload, headers=headers_a)
    assert res_doc.status_code == 403
    assert res_doc.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
