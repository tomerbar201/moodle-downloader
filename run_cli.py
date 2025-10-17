#!/usr/bin/env python3
"""
Entry point script to run the Moodle Downloader CLI.
"""

import sys
import argparse
from src.main import download_course

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download course materials from Moodle')
    parser.add_argument('course_url', help='Course URL')
    parser.add_argument('username', help='Username')
    parser.add_argument('password', help='Password')
    parser.add_argument('download_folder', help='Download folder path')
    parser.add_argument('--no-headless', action='store_true', help='Run browser in visible mode')
    parser.add_argument('--no-organize', action='store_true', help='Do not organize by section')
    parser.add_argument('--course-name', help='Course name (optional)')
    parser.add_argument('--year-range', default='2024-25', help='Year range (default: 2024-25)')
    
    args = parser.parse_args()
    
    success = download_course(
        course_url=args.course_url,
        username=args.username,
        password=args.password,
        download_folder=args.download_folder,
        headless=not args.no_headless,
        organize_by_section=not args.no_organize,
        course_name=args.course_name,
        year_range=args.year_range
    )
    
    sys.exit(0 if success else 1)
