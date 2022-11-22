"""
Helpers for Selenium driver.
By: ProgrammingIncluded
"""

# std
from typing import List

# selenium
from selenium import webdriver

def remove_elements(driver: webdriver , elements: List[str], remove_parent: bool = True):
    elements = ["'{}'".format(v) for v in elements]
    if remove_parent:
        # Some weird elements are better removing parent to
        # remove render artifacts.
        driver.execute_script("""
        const values = [{}];
        for (let i = 0; i < values.length; ++i) {{
            var element = document.querySelector(`[data-testid='${{values[i]}}']`);
            if (element)
                element.parentNode.parentNode.removeChild(element.parentNode);
        }}
        """.format(",".join(elements)))

    driver.execute_script("""
    const values = [{}];
    for (let i = 0; i < values.length; ++i) {{
        var element = document.querySelector(`[data-testid='${{values[i]}}']`);
        if (element)
            element.parentNode.removeChild(element);
    }}
    """.format(",".join(elements)))

def remove_ads(driver: webdriver) -> bool:
    return driver.execute_script("""
        var elems = document.querySelectorAll("*"),
            res = Array.from(elems).find(v => v.textContent == 'Promoted Tweet');

        if (res) {
            let p = res.parentNode.parentNode.parentNode;
            p.innerHTML="";
            return true;
        }
        return false;
    """)
