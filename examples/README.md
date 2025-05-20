# Kwork Parser Example

This example demonstrates how to use the KworkParser to extract project information from Kwork.ru.

## Prerequisites

1. Python 3.7+
2. Chrome browser installed
3. ChromeDriver installed and added to PATH (or update the path in the example)

## Installation

1. Install the required packages:

```bash
pip install selenium beautifulsoup4 webdriver-manager
```

## Usage

Run the example script:

```bash
python examples/kwork_parser_example.py
```

## Features

- Extracts project title, URL, category, and price
- Handles different price formats
- Robust error handling and logging
- Headless browser mode for server use

## Output Example

```
--- Project 1 ---
Title: Need a website design
URL: https://kwork.ru/projects/1234567
Category: Web Development
Price: 5000-10000

--- Project 2 ---
Title: Logo design needed
URL: https://kwork.ru/projects/7654321
Category: Design
Price: 3000-5000

=== Parsed 2 projects ===
1. Need a website design - 5000-10000
2. Logo design needed - 3000-5000
```

## Customization

You can modify the `parse_kwork_projects` function in the example to:
- Change the number of projects to parse
- Add more fields to extract
- Save results to a file or database
- Add pagination support
