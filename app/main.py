from typing import List

from app.common import example_generator as ex

# from app.common import models

from app.database import crud, models, schemas
from app.database.database import SessionLocal, engine

from fastapi import FastAPI, Body, Depends, HTTPException
from fastapi.routing import JSONResponse

from sqlalchemy.orm import Session
from starlette import status


models.Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="WebSch",
    description="A Scheduler for a distributed Web Fetcher System",
    version="0.0.3",
    redoc_url=None,
)


# Dependency
def get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()


# Crawler
@app.get(
    "/crawlers/",
    response_model=List[schemas.Crawler],
    tags=["Crawler"],
    summary="List all created Crawlers",
    response_description="A List of all Crawler in the Database",
)
def read_crawler(db: Session = Depends(get_db)):
    """
    List all Crawler
    """
    all_crawler = crud.get_all_crawler(db)
    return all_crawler


@app.post(
    "/crawlers/",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.Crawler,
    response_model_exclude_unset=True,
    tags=["Crawler"],
    summary="Create a crawler",
    response_description="Information about the newly created crawler",
)
def register_crawler(crawler: schemas.CreateCrawler, db: Session = Depends(get_db)):
    """
    Create a Crawler

    - **contact**: The e-mail address of the crawlers owner
    - **name**: A unique Name per Owner
    - **name**: A unique name for the crawler per contact
    - **location** (optional): The location where the crawler resides
    - **pref_tld** (optional): The Top-Level-Domain, which the crawler prefers to crawl
    """
    new_crawler = crud.create_crawler(db, crawler)
    return new_crawler


@app.put(
    "/crawlers/",
    status_code=status.HTTP_200_OK,
    response_model=schemas.Crawler,
    response_model_exclude_unset=True,
    tags=["Crawler"],
    summary="Reset crawler information",
    response_description="Information about the crawler",
)
def update_crawler(crawler: schemas.UpdateCrawler, db: Session = Depends(get_db)):
    """
    Update a Crawler - Unprovided Fields will be reset

    - **crawler_uuid**: The crawlers UUID to update
    - **contact**: The e-mail address of the crawlers owner
    - **location** (optional): The location where the crawler resides
    - **pref_tld** (optional): The Top-Level-Domain, which the crawler prefers to crawl
    """
    updated_crawler = crud.update_crawler(db, crawler)
    return updated_crawler


@app.patch(
    "/crawlers/",
    status_code=200,
    response_model=schemas.Crawler,
    response_model_exclude_unset=True,
    tags=["Crawler"],
    summary="Update a crawler",
    response_description="Information about the updated created crawler"
)
def patch_crawler(crawler: schemas.UpdateCrawler, db: Session = Depends(get_db)):
    """
    Update a Crawler -  Unprovided Fields will be ignored

    - **crawler_uuid**: The crawlers UUID to update
    - **contact**: The e-mail address of the crawlers owner
    - **location** (optional): The location where the crawler resides
    - **pref_tld** (optional): The Top-Level-Domain, which the crawler prefers to crawl
    """

    patched_crawler = crud.patch_crawler(db, crawler)
    return patched_crawler


@app.delete(
    "/crawlers/",
    tags=["Crawler"],
    summary="Delete a Crawler",
    response_description="No Content",
)
def delete_crawler(crawler: schemas.DeleteCrawler, db: Session = Depends(get_db)):
    """
    Delete a specific Crawler

    - **uuid**: UUID of the crawler, which has to be deleted
    """
    crud.delete_crawler(db, crawler)
    return JSONResponse(content=None, status_code=status.HTTP_204_NO_CONTENT)

############################
# ToDo Check: This is old Stuff
#

#
#
#
#
#
# @app.post(
#     "/frontiers/",
#     response_model=models.Frontier,
#     tags=["Frontier"],
#     summary="Get URL-Lists",
#     response_description="The received URL-Lists",
# )
# async def get_frontier(
#     request: models.CrawlRequest = Body(
#         ...,
#         example={
#             "crawler_uuid": "12345678-90ab-cdef-0000-000000000000",
#             "amount": 5,
#             "length": 3,
#             "tld": None,
#         }
#         )
# ):
#     """
#     Get a Sub List of the global Frontier
#
#     - **crawler_uuid**: Your crawlers UUID
#     - **amount**: The amount of URL-Lists you want to receive
#     - **length**: The amount of URLs in each list
#     - **tld** (optional): Filter the Response to contain only URLs of this Top-Level-Domain
#     """
#     example_urls = ex.generate_frontier(
#         request.crawler_uuid, request.amount, request.length, request.tld
#     )
#
#     return example_urls
