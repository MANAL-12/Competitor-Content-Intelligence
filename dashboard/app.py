import sys
from pathlib import Path

import pandas as pd
import streamlit as st


# ============================================================
# PATH SETUP
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from database.db import (
    initialize_database,
    get_all_articles,
    get_monitoring_status
)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Competitor Content Intelligence",
    page_icon="🔎",
    layout="wide"
)


# ============================================================
# DATABASE
# ============================================================

initialize_database()


# ============================================================
# LOAD DATA
# ============================================================

articles = get_all_articles()

monitoring_status = get_monitoring_status()


# Convert article data to DataFrame

if articles:

    df = pd.DataFrame(articles)

else:

    df = pd.DataFrame()


# Convert monitoring data to DataFrame

if monitoring_status:

    monitoring_df = pd.DataFrame(
        monitoring_status,
        columns=[
            "Competitor",
            "Website URL",
            "Last Checked",
            "Last Successful Check",
            "Failed Checks",
            "Total Checks"
        ]
    )

else:

    monitoring_df = pd.DataFrame(
        columns=[
            "Competitor",
            "Website URL",
            "Last Checked",
            "Last Successful Check",
            "Failed Checks",
            "Total Checks"
        ]
    )


# ============================================================
# TITLE
# ============================================================

st.title("🔎 Competitor Content Intelligence")

st.caption(
    "Real-time competitor content monitoring and detection dashboard"
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Dashboard Controls")

if st.sidebar.button("🔄 Refresh Dashboard"):

    st.rerun()


# ============================================================
# TOP-LEVEL METRICS
# ============================================================

total_articles = len(df)

total_competitors = len(monitoring_df)

if not monitoring_df.empty:

    online_competitors = int(
        (
            monitoring_df["Failed Checks"] == 0
        ).sum()
    )

    failed_checks = int(
        monitoring_df["Failed Checks"].sum()
    )

else:

    online_competitors = 0
    failed_checks = 0


if not df.empty and "source_type" in df.columns:

    rss_articles = int(
        (df["source_type"] == "rss").sum()
    )

    sitemap_articles = int(
        (df["source_type"] == "sitemap").sum()
    )

    direct_articles = int(
        (df["source_type"] == "direct").sum()
    )

else:

    rss_articles = 0
    sitemap_articles = 0
    direct_articles = 0


col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "Total Articles",
        total_articles
    )

with col2:

    st.metric(
        "Competitors",
        total_competitors
    )

with col3:

    st.metric(
        "Online",
        online_competitors
    )

with col4:

    st.metric(
        "Failed Checks",
        failed_checks
    )


st.divider()


# ============================================================
# COMPETITOR MONITORING STATUS
# ============================================================

st.header("🌐 Competitor Monitoring Status")

if monitoring_df.empty:

    st.info(
        "No monitoring checks have been recorded yet."
    )

else:

    display_df = monitoring_df.copy()

    # Convert timestamps to readable format

    for column in [
        "Last Checked",
        "Last Successful Check"
    ]:

        display_df[column] = pd.to_datetime(
            display_df[column],
            errors="coerce",
            utc=True
        )

        display_df[column] = (
            display_df[column]
            .dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        )


    # Add status

    display_df["Status"] = display_df.apply(
        lambda row:
        "🟢 Online"
        if row["Failed Checks"] == 0
        else "🔴 Attention",
        axis=1
    )


    status_columns = [
        "Competitor",
        "Status",
        "Last Checked",
        "Last Successful Check",
        "Failed Checks",
        "Total Checks"
    ]


    st.dataframe(
        display_df[status_columns],
        use_container_width=True,
        hide_index=True
    )


# ============================================================
# MONITORING SUMMARY
# ============================================================

st.subheader("Monitoring Summary")

summary_col1, summary_col2, summary_col3 = st.columns(3)

with summary_col1:

    st.metric(
        "Configured Competitors",
        total_competitors
    )

with summary_col2:

    st.metric(
        "Successful Competitors",
        online_competitors
    )

with summary_col3:

    st.metric(
        "Total Failed Checks",
        failed_checks
    )


st.divider()


# ============================================================
# ARTICLE DETECTION PERFORMANCE
# ============================================================

st.header("⏱️ Detection Performance")


if (
    not df.empty
    and "detection_delay_seconds" in df.columns
):

    delay_df = df.copy()

    delay_df[
        "detection_delay_seconds"
    ] = pd.to_numeric(
        delay_df["detection_delay_seconds"],
        errors="coerce"
    )

    valid_delays = delay_df[
        delay_df["detection_delay_seconds"]
        .notna()
    ]


    if not valid_delays.empty:

        average_delay = (
            valid_delays[
                "detection_delay_seconds"
            ].mean()
        )

        fastest_delay = (
            valid_delays[
                "detection_delay_seconds"
            ].min()
        )

        slowest_delay = (
            valid_delays[
                "detection_delay_seconds"
            ].max()
        )


        delay_col1, delay_col2, delay_col3 = st.columns(3)


        with delay_col1:

            st.metric(
                "Average Detection Delay",
                f"{average_delay:.2f} sec"
            )


        with delay_col2:

            st.metric(
                "Fastest Detection",
                f"{fastest_delay:.2f} sec"
            )


        with delay_col3:

            st.metric(
                "Slowest Detection",
                f"{slowest_delay:.2f} sec"
            )

    else:

        st.info(
            "Detection delay data is not available yet."
        )

else:

    st.info(
        "Detection delay data is not available yet."
    )


st.divider()


# ============================================================
# FILTERS
# ============================================================

st.header("📰 Article Intelligence")


if not df.empty:

    filtered_df = df.copy()


    # Competitor filter

    if "source_name" in filtered_df.columns:

        competitors = sorted(
            filtered_df[
                "source_name"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        selected_competitor = st.selectbox(
            "Filter by competitor",
            ["All"] + competitors
        )

        if selected_competitor != "All":

            filtered_df = filtered_df[
                filtered_df[
                    "source_name"
                ] == selected_competitor
            ]


    # Detection method filter

    if "detection_method" in filtered_df.columns:

        methods = sorted(
            filtered_df[
                "detection_method"
            ]
            .dropna()
            .unique()
            .tolist()
        )

        selected_method = st.selectbox(
            "Filter by detection method",
            ["All"] + methods
        )

        if selected_method != "All":

            filtered_df = filtered_df[
                filtered_df[
                    "detection_method"
                ] == selected_method
            ]


    # Search

    search_text = st.text_input(
        "Search article title"
    )

    if search_text:

        filtered_df = filtered_df[
            filtered_df["title"]
            .fillna("")
            .str.contains(
                search_text,
                case=False,
                na=False
            )
        ]


else:

    filtered_df = pd.DataFrame()


# ============================================================
# ARTICLE STATISTICS
# ============================================================

if not filtered_df.empty:

    stat1, stat2, stat3 = st.columns(3)


    with stat1:

        st.metric(
            "RSS Articles",
            int(
                (
                    filtered_df["source_type"]
                    == "rss"
                ).sum()
            )
        )


    with stat2:

        st.metric(
            "Sitemap Articles",
            int(
                (
                    filtered_df["source_type"]
                    == "sitemap"
                ).sum()
            )
        )


    with stat3:

        st.metric(
            "Direct Articles",
            int(
                (
                    filtered_df["source_type"]
                    == "direct"
                ).sum()
            )
        )


# ============================================================
# COMPETITOR CHART
# ============================================================

if (
    not filtered_df.empty
    and "source_name" in filtered_df.columns
):

    st.subheader("Articles by Competitor")

    competitor_counts = (
        filtered_df[
            "source_name"
        ]
        .value_counts()
    )

    st.bar_chart(
        competitor_counts
    )


# ============================================================
# DETECTION METHOD CHART
# ============================================================

if (
    not filtered_df.empty
    and "detection_method" in filtered_df.columns
):

    st.subheader("Articles by Detection Method")

    method_counts = (
        filtered_df[
            "detection_method"
        ]
        .value_counts()
    )

    st.bar_chart(
        method_counts
    )


st.divider()


# ============================================================
# LATEST ARTICLES
# ============================================================

st.header("🆕 Latest Detected Articles")


if not filtered_df.empty:

    latest_df = filtered_df.copy()


    if "first_detected_at" in latest_df.columns:

        latest_df[
            "first_detected_at"
        ] = pd.to_datetime(
            latest_df[
                "first_detected_at"
            ],
            errors="coerce",
            utc=True
        )

        latest_df = latest_df.sort_values(
            "first_detected_at",
            ascending=False
        )


    columns_to_show = [
        "title",
        "source_name",
        "detection_method",
        "published_at",
        "first_detected_at",
        "detection_delay_seconds"
    ]


    available_columns = [
        column
        for column in columns_to_show
        if column in latest_df.columns
    ]


    st.dataframe(
        latest_df[
            available_columns
        ].head(20),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No articles match the selected filters."
    )


st.divider()


# ============================================================
# ARTICLE DETAILS
# ============================================================

st.header("🔍 Article Details")


if not filtered_df.empty:

    title_options = (
        filtered_df["title"]
        .fillna("Untitled")
        .tolist()
    )

    selected_title = st.selectbox(
        "Select an article",
        title_options
    )


    selected_rows = filtered_df[
        filtered_df["title"].fillna(
            "Untitled"
        ) == selected_title
    ]


    if not selected_rows.empty:

        article = selected_rows.iloc[0]


        st.subheader(
            article.get(
                "title",
                "Untitled"
            )
        )


        detail_col1, detail_col2 = st.columns(2)


        with detail_col1:

            st.write(
                "**Competitor:**",
                article.get(
                    "source_name",
                    "N/A"
                )
            )

            st.write(
                "**Detection Method:**",
                article.get(
                    "detection_method",
                    "N/A"
                )
            )

            st.write(
                "**Source Type:**",
                article.get(
                    "source_type",
                    "N/A"
                )
            )

            st.write(
                "**Author:**",
                article.get(
                    "author",
                    "N/A"
                )
            )


        with detail_col2:

            st.write(
                "**Published:**",
                article.get(
                    "published_at",
                    "N/A"
                )
            )

            st.write(
                "**First Detected:**",
                article.get(
                    "first_detected_at",
                    "N/A"
                )
            )

            delay = article.get(
                "detection_delay_seconds"
            )

            if pd.notna(delay):

                st.write(
                    "**Detection Delay:**",
                    f"{float(delay):.2f} seconds"
                )

            else:

                st.write(
                    "**Detection Delay:**",
                    "N/A"
                )


        article_url = article.get(
            "url"
        )

        if article_url:

            st.markdown(
                f"[Open Original Article]({article_url})"
            )


        image_url = article.get(
            "image_url"
        )

        if image_url:

            try:

                st.image(
                    image_url,
                    caption="Article Image"
                )

            except Exception:

                st.info(
                    "Article image could not be displayed."
                )


        summary = article.get(
            "summary"
        )

        if summary:

            st.subheader("Summary")

            st.write(summary)


else:

    st.info(
        "No article details are available."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Competitor Blog Spy & Real-Time Content Monitoring System"
)