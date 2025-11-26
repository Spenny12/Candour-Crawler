import streamlit as st
import advertools as adv
import pandas as pd

# Set the page configuration for a wider layout
st.set_page_config(layout="wide")

# Use st.cache_data to cache the results, which prevents the crawl 
# from running again if the user interacts with the app (e.g., changes the URL)
# unless the input parameters change.
@st.cache_data(show_spinner=False)
def run_crawler_df(start_url: str) -> pd.DataFrame | None:
    """
    Runs the advertools web crawler on the provided starting URL.
    The crawl is now unlimited by page count or depth, running until all 
    internal pages are found or it hits a timeout/resource limit.
    """
    
    # Ensure the URL is valid
    if not start_url.startswith(('http://', 'https://')):
        st.error("Invalid URL: Please include 'http://' or 'https://'.")
        return None

    st.warning(
        f"Starting unlimited crawl for: `{start_url}`.\n\n"
        f"**WARNING:** The crawl is now **unlimited** in page count and depth, limited only to the **same hostname**. This may take a long time or consume significant resources for large websites. The app respects the domain's `robots.txt` file."
    )

    try:
        # adv.crawl_df crawls and returns a DataFrame directly.
        # 'same_netloc': True ensures we only follow internal links (on the same domain).
        # CLOSESPIDER_PAGECOUNT and DEPTH_LIMIT are removed to allow an unlimited crawl.
        df = adv.crawl_df(
            url_list=[start_url],
            settings={
                'LOG_LEVEL': 'WARNING',
                'ROBOTSTXT_OBEY': True, # Always respect robots.txt
            }
        )
        return df
    except Exception as e:
        st.error(f"An error occurred during crawling. Ensure the URL is correct and accessible. Error: {e}")
        return None


def main():
    """Main Streamlit application function."""
    
    st.title("🌐 Advertools Hostname HTTP Status Reporter")
    st.markdown("Enter a starting URL to crawl links on the same domain and report their HTTP response codes.")

    # 1. Input Field
    domain = st.text_input(
        "Enter the starting URL (e.g., https://advertools.readthedocs.io/)", 
        "https://advertools.readthedocs.io/",
        help="The crawl will be limited to this domain's hostname."
    )

    # 2. Crawl Button
    crawl_button = st.button("Start Crawl and Generate Report 🚀")
    
    # 3. Execution Logic
    if crawl_button and domain:
        # Clear existing cache data related to the function before starting a new crawl
        st.cache_data.clear() 

        with st.spinner("Crawling in progress... Please wait."):
            df_results = run_crawler_df(domain)
        
        if df_results is not None and not df_results.empty:
            st.success(f"Crawl completed successfully. Found {len(df_results)} URLs.")
            
            # Filter the DataFrame to show only URL and status code
            report_df = df_results[['url', 'status']].copy()
            report_df.rename(columns={'url': 'URL', 'status': 'HTTP Status Code'}, inplace=True)
            
            # 4. Display Results
            
            st.subheader("HTTP Status Code Breakdown")
            
            # Status Code Summary
            status_summary = report_df['HTTP Status Code'].value_counts().reset_index()
            status_summary.columns = ['HTTP Status Code', 'Count']
            
            # Add a description for common status codes
            def get_status_description(code):
                descriptions = {
                    200: 'OK (Success)',
                    301: 'Moved Permanently (Redirect)',
                    302: 'Found (Temporary Redirect)',
                    404: 'Not Found',
                    500: 'Internal Server Error',
                }
                return descriptions.get(code, 'Other')
            
            status_summary['Description'] = status_summary['HTTP Status Code'].apply(get_status_description)
            
            st.dataframe(
                status_summary, 
                use_container_width=True,
                column_config={
                    "HTTP Status Code": st.column_config.NumberColumn(format="%d"),
                    "Count": st.column_config.ProgressColumn("Count", format="%f", max_value=status_summary['Count'].max()),
                }
            )

            st.subheader("Detailed URL Report")
            st.dataframe(
                report_df, 
                use_container_width=True,
                hide_index=True,
                column_config={
                    "URL": st.column_config.TextColumn(width="large"),
                    "HTTP Status Code": st.column_config.TextColumn(width="small"),
                }
            )
            
            # Download button for the full results
            csv_data = report_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Full CSV Report",
                data=csv_data,
                file_name=f'crawl_report_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.csv',
                mime='text/csv',
            )
            
        elif df_results is not None and df_results.empty:
             st.warning("Crawl completed, but no internal URLs were found on the starting page.")
        # Error case handled inside the run_crawler_df function

if __name__ == "__main__":
    main()
