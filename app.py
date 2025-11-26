import streamlit as st
import advertools as adv
import pandas as pd
import tempfile
import os # Added for file operations

# Set the page configuration for a wider layout
st.set_page_config(layout="wide")

# Use st.cache_data to cache the results, which prevents the crawl
# from running again if the user interacts with the app (e.g., changes the URL)
# unless the input parameters change.
@st.cache_data(show_spinner=False)
def run_crawler_df(start_url: str) -> pd.DataFrame | None:
    """
    Runs the advertools web crawler on the provided starting URL.
    Refactored the crawl call to pass settings directly as keyword arguments
    and removed the incompatible 'LOG_LEVEL' and 'ROBOTSTXT_OBEY' arguments.
    """

    # Ensure the URL is valid
    if not start_url.startswith(('http://', 'https://')):
        st.error("Invalid URL: Please include 'http://' or 'https://'.")
        return None

    st.warning(
        f"Starting unlimited crawl for: `{start_url}`.\n\n"
        f"**WARNING:** The crawl is now **unlimited** in page count and depth, limited only to the **same hostname**. This may take a long time or consume significant resources for large websites. The crawl relies on the default settings of `advertools` to respect `robots.txt`."
    )

    # Initialize variables for cleanup
    temp_filepath = None
    df = None

    try:
        # 1. Create a unique temporary file path for the crawl output
        with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as tmp:
            temp_filepath = tmp.name

        # 2. Run the crawl, writing results to the temporary file
        # FIX: Removed ROBOTSTXT_OBEY as it is incompatible in this version
        adv.crawl(
            url_list=[start_url],
            output_file=temp_filepath,
        )

        # 3. Read the results from the temporary file into a DataFrame
        df = adv.read_jsonl(temp_filepath)

        return df

    except Exception as e:
        # Provide a more specific error message based on the reported issue
        st.error(f"An error occurred during crawling. Please check the URL and your installed advertools version. Error details: {e}")
        return None

    finally:
        # 4. Clean up the temporary file regardless of success or failure
        if temp_filepath and os.path.exists(temp_filepath):
             os.remove(temp_filepath)


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
