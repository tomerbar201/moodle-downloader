# Moodle Course Downloader

This tool helps you download all the content from your Moodle courses with a simple graphical interface. It logs into your Moodle account, finds your courses, and downloads all the files, folders, and other resources for you.

## Features

- **Easy to use**: A simple GUI to get you started quickly.
- **Automated Downloads**: Logs in and downloads content from all your courses automatically.
- **Organized Files**: Saves all downloaded content in a structured way on your computer.
- **Handles Zip Files**: Automatically extracts zipped folders that you download.

## How to Get Started

1.  **Set up your environment**:
    It's a good idea to use a virtual environment to keep things tidy.

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

2.  **Install what's needed**:
    This will install all the Python packages the tool needs to run.

    ```powershell
    pip install -r requirements.txt
    ```

3.  **Install the web drivers**:
    The tool uses Playwright to control a web browser. This command will download the necessary browser files.

    ```powershell
    python -m playwright install
    ```

4.  **Run the app**:
    You're all set! Start the application with this command.
    ```powershell
    python moodledown_gui.py
    ```

## Future Ideas

Here are some things that could be added in the future:

- Automated tests to make sure everything works as expected.
- A way to choose where to save the downloaded files from the app.
- A complete redesing for a UI that will interact with the course page as you go.
