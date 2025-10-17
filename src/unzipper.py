import os
import zipfile
import argparse
import sys
import time # Added for potential throttling if needed

def unzip_recursive(folder_path, status_callback=None):

    if not os.path.isdir(folder_path):
        message = f"Error: Folder not found or is not a directory: {folder_path}"
        if status_callback:
            status_callback(message)
        else:
            print(message)
        return 0, 0, 0

    abs_folder_path = os.path.abspath(folder_path)
    start_message = f"Starting recursive unzip in: {abs_folder_path}"
    if status_callback:
        status_callback(start_message)
    else:
        print(start_message)
        print("-" * 30)

    found_zips = 0
    extracted_count = 0
    error_count = 0

    try:
        for dirpath, dirnames, filenames in os.walk(folder_path):
            # Filter out potential recursion into extracted directories if named '.zip'
            # dirnames[:] = [d for d in dirnames if not d.lower().endswith('.zip')] # Optional: Prevent recursion into dirs named like zips

            for filename in filenames:
                if filename.lower().endswith('.zip'):
                    found_zips += 1
                    zip_filepath = os.path.join(dirpath, filename)
                    # Extract in the same directory as the zip file
                    extract_to_dir = dirpath

                    status_msg = f"Found: {os.path.relpath(zip_filepath, folder_path)}"
                    if status_callback: status_callback(status_msg)
                    else: print(status_msg)

                    try:
                        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
                            # Add a small delay/yield if UI becomes unresponsive on huge archives
                            # time.sleep(0.01) # Example - usually not needed
                            zip_ref.extractall(extract_to_dir)
                        status_msg = f"  Extracted: {filename}"
                        if status_callback: status_callback(status_msg)
                        else: print(status_msg)
                        extracted_count += 1
                        # Optionally, delete the zip file after successful extraction
                        # os.remove(zip_filepath)
                    except zipfile.BadZipFile:
                        error_msg = f"  Error: Corrupt zip file - {filename}"
                        if status_callback: status_callback(error_msg)
                        else: print(error_msg)
                        error_count += 1
                    except PermissionError:
                        error_msg = f"  Error: Permission denied for {filename}"
                        if status_callback: status_callback(error_msg)
                        else: print(error_msg)
                        error_count += 1
                    except Exception as e:
                        error_msg = f"  Error: Unexpected error extracting {filename}: {e}"
                        if status_callback: status_callback(error_msg)
                        else: print(error_msg)
                        error_count += 1
                    # Add a small delay between files if needed
                    # time.sleep(0.05)
            # Process events if called from GUI thread often (better to use worker thread)
            # QApplication.processEvents() # Only if running in main thread, not ideal
    except Exception as walk_err:
         error_msg = f"Error during directory walk: {walk_err}"
         if status_callback: status_callback(error_msg)
         else: print(error_msg)
         error_count += 1 # Count this as an error

    summary_message = (f"Unzip finished. Found: {found_zips}, Extracted: {extracted_count}, Errors: {error_count}")
    if status_callback:
        status_callback(summary_message)
    else:
        print("\n" + "=" * 30)
        print("Unzip process completed.")
        print(f"Total .zip files found: {found_zips}")
        print(f"Successfully extracted: {extracted_count}")
        print(f"Errors encountered: {error_count}")
        print("=" * 30)

    return found_zips, extracted_count, error_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recursively unzip all .zip files within a specified folder and its subfolders."
    )
    parser.add_argument(
        "folder",
        metavar="FOLDER_PATH",
        type=str,
        help="The path to the folder containing .zip files."
    )
    args = parser.parse_args()
    target_directory = os.path.abspath(args.folder)
    # Run with console printing
    unzip_recursive(target_directory)

