"""Streamlit dashboard entry point. Run with `pulse dashboard`."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from aiml_pulse import storage, trends


def main() -> None:
    st.set_page_config(page_title="AI/ML Pulse", layout="wide")
    st.title("AI/ML Pulse")
    st.caption(f"Local snapshot · {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    items_total = storage.count_items()
    st.metric("Items ingested", items_total)

    st.subheader("Source distribution")
    rows = storage.source_distribution()
    if rows:
        df = pd.DataFrame(rows, columns=["source", "count"])
        fig = px.pie(df, names="source", values="count", hole=0.4)
        st.plotly_chart(fig, width="content")
    else:
        st.info("No items yet — run `pulse fetch`.")

    st.subheader("Trending topics")
    trending = trends.trending_topics()
    if trending:
        df = pd.DataFrame(trending)
        st.dataframe(df, width="content")
    else:
        st.info("No topic snapshots yet.")

    st.subheader("Search")
    query = st.text_input("Query (FTS5)")
    if query:
        results = storage.search_items(query, limit=25)
        for item in results:
            st.markdown(f"- [{item.title}]({item.url})  \n  *{item.source.value} · {item.published_at:%Y-%m-%d}*")
    else:
        st.caption("Type a query above to search titles + summaries.")

    st.subheader("Recent items")
    since = datetime.now() - timedelta(days=14)
    recent = storage.get_items_since(since)
    if recent:
        df = pd.DataFrame(
            [
                {
                    "published": item.published_at,
                    "source": item.source.value,
                    "title": item.title,
                    "score": item.score,
                    "url": str(item.url),
                }
                for item in recent[:100]
            ]
        )
        st.dataframe(df, width="content")


if __name__ == "__main__":
    main()
