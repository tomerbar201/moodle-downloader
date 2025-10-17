"""
Test script for course_extractor module
"""

from src.course_extractor import extract_courses

# Sample HTML similar to Moodle dashboard structure
sample_html = html_data = """
<section id="inst310297" class=" block_myoverview block item1 card mb-3" role="region" data-block="myoverview" data-instance-id="310297" aria-labelledby="instance-310297-header">
    <div class="card-body p-3">
        <h5 id="instance-310297-header" class="card-title d-inline">הקורסים שלי</h5>
        <div class="card-text content mt-3">
            <div id="block-myoverview-68f2230a9698e68f2230a969901" class="block-myoverview block-cards" data-region="myoverview" role="navigation" data-init="true">
                <div id="courses-view-68f2230a9698e68f2230a969901">
                    <div id="page-container-7">
                        <div data-region="paged-content-page" data-page="1">
                            <ul class="list-group">
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=2098" class="aalink coursename">
                                                <span class="sr-only">Course is starred</span>
                                                עקרונות ויישומים בניתוח סטטיסטי
                                            </a>
                                        </div>
                                    </div>
                                </li>
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=2105" class="aalink coursename">
                                                מבני נתונים ואלגוריתמים
                                            </a>
                                        </div>
                                    </div>
                                </li>
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=517" class="aalink coursename">
                                                מבוא לחקר השפה
                                            </a>
                                        </div>
                                    </div>
                                </li>
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=532" class="aalink coursename">
                                                חישוביות וקוגניציה
                                            </a>
                                        </div>
                                    </div>
                                </li>
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=516" class="aalink coursename">
                                                סמינריון לבוגר 
                                            </a>
                                        </div>
                                    </div>
                                </li>
                                <li class="list-group-item course-listitem">
                                    <div class="row">
                                        <div class="col-md-9 d-flex flex-column">
                                            <a href="https://moodle.huji.ac.il/2024-25/course/view.php?id=543" class="aalink coursename">
                                                נוירוביולוגיה של התפתחות ולמידה
                                            </a>
                                        </div>
                                    </div>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</section>
"""

def test_extract_courses():
    """Test the extract_courses function with sample HTML."""
    print("Testing course extraction...")
    
    courses = extract_courses(sample_html)
    
    print(f"\nExtracted {len(courses)} courses:")
    for i, course in enumerate(courses, 1):
        print(f"{i}. {course['name']}")
        print(f"   URL: {course['href']}")
    
    # Verify results
    assert len(courses) == 6, f"Expected 6 courses, got {len(courses)}"
    assert courses[0]['name'].strip() == "עקרונות ויישומים בניתוח סטטיסטי"
    assert "id=2098" in courses[0]['href']
    assert courses[1]['name'].strip() == "מבני נתונים ואלגוריתמים"
    assert "id=2105" in courses[1]['href']
    assert courses[5]['name'].strip() == "נוירוביולוגיה של התפתחות ולמידה"
    assert "id=543" in courses[5]['href']
    
    print("\n[PASS] All tests passed!")

def test_empty_html():
    """Test with HTML that has no courses."""
    print("\nTesting with empty HTML...")
    
    empty_html = "<html><body><div id='other-section'></div></body></html>"
    courses = extract_courses(empty_html)
    
    assert len(courses) == 0, f"Expected 0 courses, got {len(courses)}"
    print("[PASS] Empty HTML handled correctly")

def test_malformed_html():
    """Test with HTML that has the section but no valid links."""
    print("\nTesting with malformed HTML...")
    
    malformed_html = """
    <html><body>
        <div id="my-courses-section">
            <li class="list-group-item">
                <span>Not a link</span>
            </li>
        </div>
    </body></html>
    """
    
    courses = extract_courses(malformed_html)
    assert len(courses) == 0, f"Expected 0 courses, got {len(courses)}"
    print("[PASS] Malformed HTML handled correctly")

if __name__ == "__main__":
    try:
        test_extract_courses()
        print("1")
        test_empty_html()
        print("2")
        test_malformed_html()
        print("3")
        print("\n" + "="*50)
        print("All tests completed successfully!")
        print("="*50)
    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
    except Exception as e:
        print(f"\n[ERROR] Error during testing: {e}")
