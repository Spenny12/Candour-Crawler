import streamlit as st
import advertools as adv
import pandas as pd
import tempfile
import os
import json
import multiprocessing # NEW: For running the crawl in a separate process
import time # NEW: For polling the output file

# Set the page configuration for a wider layout
st.set_page_config(layout="wide")


# New function to run the blocking crawl in a separate process.
# This target function prevents the main Streamlit thread from blocking.
def _run_adv_crawl_target(start_url: str, temp_filepath: str):
    """Target function for the multiprocessing Process."""
    try:
        adv.crawl(
            url_list=[start_url],
            output_file=temp_filepath,
            follow_links=True
        )
    except Exception as e:
        # In a real-time scenario, errors in the child process are logged
        # and the main process will detect the failure when the file is incomplete.
        print(f"Crawler process failed with error: {e}")

# The main processing function - removed @st.cache_data as it is incompatible with live updates
def run_crawler_df(start_url: str) -> pd.DataFrame | None:
    """
    Runs the advertools web crawler in a background process and monitors
    the output file to provide live updates to the Streamlit UI.
    """

    # Ensure the URL is valid
    if not start_url.startswith(('http://', 'https://')):
        st.error("Invalid URL: Please include 'http://' or 'https://'.")
        return None

    st.warning(
        f"Starting live, unlimited crawl for: `{start_url}`.\n\n"
        f"**WARNING:** The crawl is now **unlimited** in page count and depth, and it is configured to **follow internal links**. It relies on default settings to restrict to the hostname and respect `robots.txt`."
    )

    # Initialize variables for cleanup
    temp_filepath = None
    df = None

    # 1. Setup the temporary file path
    with tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False) as tmp:
        temp_filepath = tmp.name

    # 2. Setup Streamlit placeholder for live updates
    live_report_placeholder = st.empty()

    # 3. Start the crawl process
    crawl_process = multiprocessing.Process(
        target=_run_adv_crawl_target,
        args=(start_url, temp_filepath)
    )
    crawl_process.start()

    st.subheader("Live Crawl Status")

    # 4. Monitoring Loop: Runs until the crawl process is finished
    while crawl_process.is_alive():
        # Check and update every 3 seconds
        time.sleep(3)

        try:
            data = []
            if os.path.exists(temp_filepath) and os.path.getsize(temp_filepath) > 0:
                with open(temp_filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        data.append(json.loads(line))

                # Update the display
                if data:
                    current_df = pd.DataFrame(data)

                    # Prepare the data for the live view
                    live_report_df = current_df[['url', 'status']].copy()
                    live_report_df.rename(columns={'url': 'URL', 'status': 'HTTP Status Code'}, inplace=True)

                    # Use the placeholder to update the UI section
                    with live_report_placeholder.container():
                        st.write(f"**Pages Crawled So Far:** {len(live_report_df)}")
                        st.dataframe(live_report_df, use_container_width=True, hide_index=True)

        except Exception as e:
            # Safely handle file access errors while the file is actively being written
            print(f"Error reading partial file: {e}")
            pass

    # Wait for the process to fully terminate
    crawl_process.join()

    # 5. After the process finishes, read the final results
    try:
        if os.path.exists(temp_filepath) and os.path.getsize(temp_filepath) > 0:
            data = []
            with open(temp_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    data.append(json.loads(line))

            df = pd.DataFrame(data)

            # Check for empty or failed crawl data
            if df.empty or 'status' not in df.columns or (df['status'] == 0).all():
                 return pd.DataFrame()

            return df
        else:
             st.error("The crawler finished but produced no output file. Check terminal logs for process errors.")
             return None

    except Exception as e:
        st.error(f"An error occurred while finalizing the report. Error: {e}")
        return None

    finally:
        # 6. Cleanup the temporary file regardless of success or failure
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
        # This will now start the live monitoring process
        with st.spinner("Crawl initiated. Starting process and monitoring output..."):
            df_results = run_crawler_df(domain)

        # After the live monitoring loop finishes, display the final, structured report
        if df_results is not None and not df_results.empty:
            st.success(f"Crawl completed successfully. Found {len(df_results)} URLs.")

            # Filter the DataFrame to show only URL and status code
            report_df = df_results[['url', 'status']].copy()
            report_df.rename(columns={'url': 'URL', 'status': 'HTTP Status Code'}, inplace=True)

            # 4. Display Final Results

            st.subheader("Final HTTP Status Code Breakdown")

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
                    "Count": st.column_config.ProgressColumn("Count", format="%f", max_value=int(status_summary['Count'].max())),
                }
            )

            st.subheader("Final Detailed URL Report")
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
