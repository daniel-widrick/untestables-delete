# TeamCity Configuration

This directory contains the TeamCity configuration for the Untestables project.

## Configuration Files

- `settings.kts`: JetBrains TeamCity configuration using Kotlin DSL
- `pipelines.yml`: TeamCity Pipelines configuration using YAML format

## TeamCity Pipelines Configuration Details

The TeamCity Pipelines configuration (`pipelines.yml`) includes:

1. A job named "Run Tests" that:
   - Sets up Python 3.11
   - Installs Poetry
   - Installs project dependencies
   - Runs the tests using the Poetry script "tests"

## Usage

To use the TeamCity Pipelines configuration:

1. Make sure you have TeamCity Pipelines set up
2. Import this project into TeamCity Pipelines
3. The pipeline will run the tests on a Linux-Medium agent

## Requirements

The pipeline requires:
- A Linux-Medium agent
- Access to install Python 3.11
- Internet access to download Poetry and dependencies
