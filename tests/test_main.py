from fastapi.testclient import TestClient
from fastapi import status

from app.main import app
from app.common import common_values as c, enum
from app.database import crud, database

from time import sleep

client = TestClient(app)
db = database.SessionLocal()


def test_get_all_crawler():
    crud.delete_crawlers(db)
    client.post(c.crawler_endpoint, json={"contact": c.test_email_1, "name": "IsaacV"})
    client.post(c.crawler_endpoint, json={"contact": c.test_email_1, "name": "IsaacVI"})
    json_response = client.get(c.crawler_endpoint).json()
    assert len(json_response) == 2


def test_create_crawler():
    crud.delete_crawlers(db)
    response = client.post(
        c.crawler_endpoint,
        json={
            "contact": "jens@honzont.de",
            "name": "IsaacIV",
            "location": "Germany",
            "tld_preference": "de",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED


def test_create_crawler_duplicate():
    crud.delete_crawlers(db)
    client.post(c.crawler_endpoint, json={"contact": c.test_email_1, "name": "IsaacIV"})
    response2 = client.post(
        c.crawler_endpoint, json={"contact": c.test_email_1, "name": "IsaacIV"}
    )
    assert response2.status_code == status.HTTP_409_CONFLICT


def test_update_crawler():
    crud.delete_crawlers(db)
    create_response = client.post(
        c.crawler_endpoint,
        json={"contact": c.test_email_1, "name": "IsaacIV", "location": "Germany"},
    ).json()
    uuid = create_response["uuid"]
    contact = create_response["contact"]
    name = "IsaacXII"
    update_response = client.put(
        c.crawler_endpoint, json={"uuid": uuid, "contact": contact, "name": name}
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["location"] is None


def test_update_unknown_crawler():
    update_response = client.put(c.crawler_endpoint, json={"uuid": c.sample_uuid},)
    assert update_response.status_code == status.HTTP_404_NOT_FOUND


def test_patch_crawler_mix():
    crud.delete_crawlers(db)
    create_response = client.post(
        c.crawler_endpoint,
        json={
            "contact": c.test_email_1,
            "name": "IsaacIV",
            "location": "Germany",
            "tld_preference": "de",
        },
    ).json()
    uuid = create_response["uuid"]
    name = "IsaacIX"

    update_response = client.patch(
        c.crawler_endpoint, json={"uuid": uuid, "name": name}
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == "IsaacIX"
    assert update_response.json()["location"] == "Germany"


def test_patch_unknown_crawler():
    patch_response = client.patch(c.crawler_endpoint, json={"uuid": c.sample_uuid},)
    assert patch_response.status_code == status.HTTP_404_NOT_FOUND


def test_patch_crawler_empty_patch():
    crud.delete_crawlers(db)
    create_response = client.post(
        c.crawler_endpoint,
        json={
            "contact": c.test_email_1,
            "name": "IsaacIII",
            "location": "Germany",
            "tld_preference": "de",
        },
    ).json()

    uuid = create_response["uuid"]
    update_response = client.patch(c.crawler_endpoint, json={"uuid": uuid})
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == "IsaacIII"
    assert update_response.json()["location"] == "Germany"
    assert update_response.json()["tld_preference"] == "de"


def test_patch_crawler_full_patch():
    crud.delete_crawlers(db)
    create_response = client.post(
        c.crawler_endpoint,
        json={
            "contact": c.test_email_1,
            "name": "IsaacXXI",
            "location": "Germany",
            "tld_preference": "de",
        },
    ).json()

    uuid = create_response["uuid"]
    update_response = client.patch(
        c.crawler_endpoint,
        json={
            "uuid": uuid,
            "name": "IsaacXXII",
            "location": "Sweden",
            "tld_preference": "se",
        },
    )
    assert update_response.status_code == status.HTTP_200_OK
    assert update_response.json()["name"] == "IsaacXXII"
    assert update_response.json()["location"] == "Sweden"
    assert update_response.json()["tld_preference"] == "se"


def test_delete_crawler():
    crud.delete_crawlers(db)
    json_response = client.post(
        c.crawler_endpoint, json={"contact": c.test_email_1, "name": "IsaacVII"}
    ).json()
    created_uuid = json_response["uuid"]
    print("UUID: {}".format(created_uuid))
    delete_response = client.delete(c.crawler_endpoint, json={"uuid": created_uuid})

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert delete_response.content == b""

    json_response = client.get(c.crawler_endpoint).json()
    assert len(json_response) == 0


def test_delete_unknown_crawler():
    crud.delete_crawlers(db)
    delete_response = client.delete(c.crawler_endpoint, json={"uuid": c.sample_uuid})

    assert delete_response.status_code == status.HTTP_404_NOT_FOUND


def test_get_db_stats():
    response = client.get(c.stats_endpoint)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == 4


def test_generate_example_db():
    before = client.get(c.stats_endpoint).json()
    response = client.post(
        c.database_endpoint,
        json={
            "crawler_amount": 1,
            "fqdn_amount": 1,
            "min_url_amount": 1,
            "max_url_amount": 1,
            "connection_amount": 1,
        },
    )
    sleep(20)
    after = client.get(c.stats_endpoint).json()
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert after["crawler_amount"] == before["crawler_amount"] + 1
    assert after["frontier_amount"] == before["frontier_amount"] + 1
    assert after["url_amount"] == before["url_amount"] + 1



def test_generate_example_frontier_wrong_initial_values():
    response = client.post(
        c.database_endpoint,
        json={
            "crawler_amount": 0,
            "fqdn_amount": 1,
            "min_url_amount": 2,
            "max_url_amount": 1,
            "connection_amount": 1,
            "visited_ratio": 0.0,
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Value 2 is larger than 1"


def test_get_simple_frontier():
    crud.delete_crawlers(db)
    new_crawler_uuid = client.post(
        c.crawler_endpoint, json={"contact": c.test_email_1, "name": "Isaac"}
    ).json()["uuid"]

    response = client.post(
        c.frontier_endpoint,
        json={"crawler_uuid": new_crawler_uuid, "amount": 1, "length": 1},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["url_frontiers_count"] == 1
    assert response.json()["urls_count"] == 1


def test_get_simple_frontier_with_bad_uuid():
    crud.delete_crawlers(db)
    response = client.post(
        c.frontier_endpoint,
        json={"crawler_uuid": c.sample_uuid, "amount": 1, "length": 1},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_frontiers():
    crud.delete_crawlers(db)
    new_crawler_uuid = client.post(
        c.crawler_endpoint, json={"contact": c.test_email_1, "name": "Isaac"}
    ).json()["uuid"]

    response1 = client.post(
        c.frontier_endpoint,
        json={
            "crawler_uuid": new_crawler_uuid,
            "amount": 1,
            "length": 1,
            "tld": enum.TLD.Commercial,
            "prio_mode": enum.PRIO.breath_first_search,
        },
    )
    assert response1.status_code == status.HTTP_200_OK
    response2 = client.post(
        c.frontier_endpoint,
        json={
            "crawler_uuid": new_crawler_uuid,
            "amount": 1,
            "length": 1,
            "tld": enum.TLD.Sweden,
            "prio_mode": enum.PRIO.random,
        },
    )

    assert response2.status_code == status.HTTP_200_OK


def test_delete_example_db():
    response = client.delete(
        c.database_endpoint,
        json={
            "delete_url_refs": True,
            "delete_crawlers": True,
            "delete_urls": True,
            "delete_fqdns": True,
        },
    )
    sleep(10)
    after = client.get(c.stats_endpoint).json()
    assert response.status_code == status.HTTP_202_ACCEPTED
    assert after["crawler_amount"] == 0
    assert after["frontier_amount"] == 0
    assert after["url_amount"] == 0
    assert after["url_ref_amount"] == 0




# def test_update_crawler_no_unique_contact_name_combination():
#     assert 1 == 0
#     # ToDo test_update_crawler_no_unique_contact_name_combination()
#