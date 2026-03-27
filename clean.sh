#!/bin/bash

# AutoCut Cleanup Script
# This script removes temporary and test outputs to keep the workspace clean.

echo "🧹 Starting cleanup..."

# 1. Remove global temporary folders (hidden)
rm -rf .zip_update_tmp
rm -rf .backup_before_zip

# 2. Remove sample inputs generated for testing
rm -rf outputs/sample_input

# 3. Remove old/test run directories
rm -rf outputs/demo_run
rm -rf outputs/demo_run2
rm -rf outputs/demo_run_zip
rm -rf outputs/final_demo
rm -rf outputs/final_demo2
rm -rf outputs/final_demo_zip
rm -rf outputs/xhs_demo
rm -rf outputs/xhs_test_fix
rm -rf outputs/autocut_project

# 4. Remove any remaining FFmpeg temp folders inside existing project dirs
find outputs -type d -name "compose_tmp" -exec rm -rf {} +
find outputs -type d -name "compose_xhs_tmp" -exec rm -rf {} +

echo "✨ Cleanup complete. Core assets in 'outputs/srt', 'outputs/input' and 'outputs/xhs_demo_srt' are preserved."
