from datetime import datetime, timedelta, timezone

from app.database import db_models, pyd_models, fetchers, database
from app.common import enum, http_exceptions as http_ex, common_values as c

from sqlalchemy.sql.expression import func
from sqlalchemy.orm import Session


def create_fqdn_list(db, request):
    fqdn_reservation_list = db.query(db_models.FetcherReservation.fqdn).filter(
        db_models.FetcherReservation.latest_return > datetime.now(tz=timezone.utc)
    )

    fqdn_list = db.query(db_models.Frontier).filter(
        db_models.Frontier.fqdn.notin_(fqdn_reservation_list)
    )

    # Filter
    if request.long_term_part_mode == enum.LONGPART.top_level_domain:
        fetcher_pref_tld = (
            db.query(db_models.Fetcher)
            .filter(db_models.Fetcher.uuid == str(request.fetcher_uuid))
            .first()
        ).tld_preference

        fqdn_list = fqdn_list.filter(db_models.Frontier.tld == fetcher_pref_tld)

    elif request.long_term_part_mode == enum.LONGPART.fqdn_hash:
        fetcher = (
            db.query(db_models.Fetcher).order_by(db_models.Fetcher.reg_date.asc()).all()
        )

        fetcher_index = next(
            (
                i
                for i, item in enumerate(fetcher)
                if item.uuid == str(request.fetcher_uuid)
            ),
            -1,
        )

        fqdn_list = fqdn_list.filter(
            db_models.Frontier.fqdn_hash_fetcher_index == fetcher_index
        )

    elif request.long_term_part_mode == enum.LONGPART.consistent_hashing:
        fetcher_hash_ranges = database.get_fetcher_hash_ranges(db, str(request.fetcher_uuid))

        filter_query = database.get_hash_range_filter_query(fetcher_hash_ranges)

        fqdn_list = fqdn_list.filter(filter_query)


    # Order
    if request.long_term_prio_mode == enum.LONGPRIO.random:
        fqdn_list = fqdn_list.order_by(func.random())

    elif request.long_term_prio_mode == enum.LONGPRIO.large_sites_first:
        fqdn_list = fqdn_list.order_by(db_models.Frontier.fqdn_url_count.desc())

    elif request.long_term_prio_mode == enum.LONGPRIO.small_sites_first:
        fqdn_list = fqdn_list.order_by(db_models.Frontier.fqdn_url_count.asc())

    elif request.long_term_prio_mode == enum.LONGPRIO.avg_pagerank:
        fqdn_list = fqdn_list.order_by(db_models.Frontier.fqdn_avg_pagerank.desc())

    elif request.long_term_prio_mode == enum.LONGPRIO.old_sites_first:
        fqdn_list = fqdn_list.order_by(db_models.Frontier.fqdn_avg_last_visited_date.asc())

    elif request.long_term_prio_mode == enum.LONGPRIO.new_sites_first:
        fqdn_list = fqdn_list.order_by(db_models.Frontier.fqdn_avg_last_visited_date.desc())

    # Limit
    if request.amount > 0:
        fqdn_list = fqdn_list.limit(request.amount)

    rv = [item for item in fqdn_list]
    return rv


def short_term_frontier(db, request, fqdn):
    db_url_list = db.query(db_models.Url).filter(db_models.Url.fqdn == fqdn.fqdn)

    # Order
    if request.short_term_prio_mode == enum.SHORTPRIO.random:
        db_url_list = db_url_list.order_by(func.random())

    elif request.short_term_prio_mode == enum.SHORTPRIO.old_pages_first:
        db_url_list = db_url_list.order_by(
            db_models.Url.url_last_visited.asc().nullsfirst()
        )

    elif request.short_term_prio_mode == enum.SHORTPRIO.new_pages_first:
        db_url_list = db_url_list.order_by(
            db_models.Url.url_last_visited.desc().nullslast()
        )

    elif request.short_term_prio_mode == enum.SHORTPRIO.pagerank:
        db_url_list = db_url_list.order_by(
            db_models.Url.url_pagerank.desc()
        )

    db_url_list = db_url_list[: request.length] if request.length > 0 else db_url_list

    return db_url_list


def long_term_frontier(fqdn, url_list):
    return pyd_models.Frontier(
        fqdn=fqdn.fqdn,
        fqdn_hash_fetcher_index=fqdn.fqdn_hash_fetcher_index,
        tld=fqdn.tld,
        url_list=url_list,
        fqdn_last_ipv4=fqdn.fqdn_last_ipv4,
        fqdn_last_ipv6=fqdn.fqdn_last_ipv6,
        fqdn_avg_pagerank=fqdn.fqdn_avg_pagerank,
        fqdn_crawl_delay=fqdn.fqdn_crawl_delay,
        fqdn_url_count=len(url_list),
    )


def get_referencing_urls(db, url, amount):
    return (
        db.query(db_models.Url)
        .filter(db_models.Url.url_last_visited is not None)
        .order_by(func.random())
        .limit(amount)
    )


def get_url_list_from_frontier_response(frontier_response):
    url_list = []
    for url_frontier in frontier_response.url_frontiers:
        url_list.extend([str(url.url) for url in url_frontier.url_list])

    return url_list


def get_fqdn_list_from_frontier_response(frontier_response):
    return [url_frontier.fqdn for url_frontier in frontier_response.url_frontiers]


def get_only_new_list_items(new_list, old_list):
    only_new_list = [item for item in new_list if item not in old_list]

    return only_new_list


def clean_reservation_list(db):
    db.query(db_models.FetcherReservation).filter(
        db_models.FetcherReservation.latest_return < datetime.now(tz=timezone.utc)
    ).delete()

    db.commit()
    return True


def save_reservations(db, frontier_response, latest_return):
    uuid = frontier_response.uuid
    fqdn_only_list = get_fqdn_list_from_frontier_response(frontier_response)

    clean_reservation_list(db)

    current_db_reservation_list = (
        db.query(db_models.FetcherReservation)
        .filter(db_models.FetcherReservation.fetcher_uuid == uuid)
        .filter(
            db_models.FetcherReservation.latest_return > datetime.now(tz=timezone.utc)
        )
    )
    current_block_list = [fqdn.fqdn for fqdn in current_db_reservation_list]

    fqdn_new_block_list = get_only_new_list_items(
        new_list=fqdn_only_list, old_list=current_block_list
    )

    new_db_block_list = [
        db_models.FetcherReservation(
            fetcher_uuid=str(uuid), fqdn=fqdn, latest_return=latest_return
        )
        for fqdn in fqdn_new_block_list
    ]

    db.bulk_save_objects(new_db_block_list)
    db.commit()
    return True


def get_fqdn_frontier(db, request: pyd_models.FrontierRequest):
    if not fetchers.uuid_exists(db, str(request.fetcher_uuid)):
        http_ex.raise_http_404(request.fetcher_uuid)

    frontier_response = pyd_models.FrontierResponse(
        uuid=str(request.fetcher_uuid),
        short_term_prio_mode=request.short_term_prio_mode,
        long_term_prio_mode=request.long_term_prio_mode,
        long_term_part_mode=request.long_term_part_mode,
    )

    fqdns = create_fqdn_list(db, request)

    for fqdn in fqdns:
        url_list = list(short_term_frontier(db, request, fqdn))

        frontier_response.urls_count += len(url_list)
        frontier_response.url_frontiers.append(long_term_frontier(fqdn, url_list))

    frontier_response.url_frontiers_count = len(frontier_response.url_frontiers)

    latest_return = datetime.now(tz=timezone.utc) + timedelta(hours=c.hours_to_die)
    save_reservations(db, frontier_response, latest_return)

    frontier_response.latest_return = latest_return
    frontier_response.response_url = c.response_url

    return frontier_response


def calculate_avg_freshness(db):
    avg_timestamps = db.query(
        func.to_timestamp(
            func.avg(func.extract("epoch", db_models.Url.url_last_visited))
        )
    ).first()
    rv = (
        avg_timestamps[0].strftime("%Y-%m-%d %H:%M:%S.%f")
        if avg_timestamps[0] is not None
        else "None"
    )
    return rv


def get_visited_ratio(db):
    visited_urls_count = (
        db.query(db_models.Url)
        .filter(db_models.Url.url_last_visited.isnot(None))
        .count()
    )
    all_urls = db.query(db_models.Url).count()
    if all_urls == 0 or all_urls is None:
        all_urls = -1
    return visited_urls_count / all_urls


def get_fqdn_hash_range(db):
    hash_counts = (
        db.query(
            db_models.Frontier.fqdn_hash_fetcher_index,
            func.count(db_models.Frontier.fqdn),
        )
        .group_by(db_models.Frontier.fqdn_hash_fetcher_index)
        .order_by(db_models.Frontier.fqdn_hash_fetcher_index)
        .all()
    )

    hash_values = [x[1] for x in hash_counts]

    if hash_values:
        count = len(hash_values)
        min_value = min(hash_values)
        max_value = max(hash_values)
        avg_value = sum(hash_values) / count

        hash_range = max_value - min_value
        perc_range = (hash_range / 2) / avg_value

    else:
        perc_range = 0.0

    return round(perc_range, 2)


def get_db_stats(db: Session):
    clean_reservation_list(db)
    response = {
        "fetcher_amount": db.query(db_models.Fetcher).count(),
        "frontier_amount": db.query(db_models.Frontier).count(),
        "url_amount": db.query(db_models.Url).count(),
        "url_ref_amount": db.query(db_models.URLRef).count(),
        "reserved_fqdn_amount": db.query(db_models.FetcherReservation)
        .filter(
            db_models.FetcherReservation.latest_return > datetime.now(tz=timezone.utc)
        )
        .count(),
        "avg_freshness": calculate_avg_freshness(db),
        "visited_ratio": get_visited_ratio(db),
        "fqdn_hash_range": get_fqdn_hash_range(db),
    }
    return response


def get_random_url(db: Session, amount: int = 1, fqdn: str = None):
    url = db.query(db_models.Url)
    if fqdn is not None:
        url = url.filter(db_models.Url.fqdn == fqdn)

    url = url.order_by(func.random()).limit(amount)

    url_list = [url for url in url]

    return pyd_models.RandomUrls(url_list=url_list)


def get_fetcher_settings(db: Session) -> pyd_models.FetcherSettings:
    fetcher_settings = db.query(db_models.FetcherSettings).first()
    return pyd_models.FetcherSettings(
        logging_mode=fetcher_settings.logging_mode,
        crawling_speed_factor=fetcher_settings.crawling_speed_factor,
        default_crawl_delay=fetcher_settings.default_crawl_delay,
        parallel_process=fetcher_settings.parallel_process,
        parallel_fetcher=fetcher_settings.parallel_fetcher,
        iterations=fetcher_settings.iterations,
        fqdn_amount=fetcher_settings.fqdn_amount,
        url_amount=fetcher_settings.url_amount,
        long_term_prio_mode=fetcher_settings.long_term_prio_mode,
        long_term_part_mode=fetcher_settings.long_term_part_mode,
        short_term_prio_mode=fetcher_settings.short_term_prio_mode,
        min_links_per_page=fetcher_settings.min_links_per_page,
        max_links_per_page=fetcher_settings.max_links_per_page,
        lpp_distribution_type=fetcher_settings.lpp_distribution_type,
        internal_vs_external_threshold=fetcher_settings.internal_vs_external_threshold,
        new_vs_existing_threshold=fetcher_settings.new_vs_existing_threshold,
    )


def settings_exists(db: Session):
    if db.query(db_models.FetcherSettings).count() == 1:
        return True
    else:
        return False


def set_fetcher_settings(request: pyd_models.FetcherSettings, db: Session):
    if not settings_exists(db):
        db_fetcher_settings = db_models.FetcherSettings(
            id=1,
            logging_mode=request.logging_mode,
            crawling_speed_factor=request.crawling_speed_factor,
            default_crawl_delay=request.default_crawl_delay,
            parallel_process=request.parallel_process,
            parallel_fetcher=request.parallel_fetcher,
            iterations=request.iterations,
            fqdn_amount=request.fqdn_amount,
            url_amount=request.url_amount,
            long_term_prio_mode=request.long_term_prio_mode,
            long_term_part_mode=request.long_term_part_mode,
            short_term_prio_mode=request.short_term_prio_mode,
            min_links_per_page=request.min_links_per_page,
            max_links_per_page=request.max_links_per_page,
            lpp_distribution_type=request.lpp_distribution_type,
            internal_vs_external_threshold=request.internal_vs_external_threshold,
            new_vs_existing_threshold=request.new_vs_existing_threshold,
        )

        db.add(db_fetcher_settings)

    else:

        reduced_request = {k: v for k, v in request.__dict__.items() if v is not None}

        db.query(db_models.FetcherSettings).filter(
            db_models.FetcherSettings.id == 1
        ).update(reduced_request)
        db.commit()

        db_fetcher_settings = (
            db.query(db_models.FetcherSettings)
            .filter(db_models.FetcherSettings.id == 1)
            .first()
        )

    db.commit()
    db.refresh(db_fetcher_settings)

    return db_fetcher_settings
