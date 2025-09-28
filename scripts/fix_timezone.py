#!/usr/bin/env python3
"""
Timezone Fix Script for aMonitoringHub
Fixes the 3-hour discrepancy between chart display and header timestamp
"""

import re
import shutil
import os
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the original file"""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def fix_timezone_issue(filepath):
    """Fix the timezone handling in the frontend"""
    
    print(f"🔧 Fixing timezone issue in {filepath}")
    
    # Read the file
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # First, let's look for the specific lines where timestamps are formatted in charts
    # We need to make the formatting consistent
    
    # Pattern 1: Chart label formatting in updateCO2HistoryChart and similar functions
    chart_label_pattern = r'window\.historyCO2Chart\.data\.labels = sorted\.map\(function\(i\)\{ return new Date\(i\.timestampUnix \* 1000\)\.toLocaleString\([^}]+\}\); \}\);'
    
    if re.search(chart_label_pattern, content):
        print("✅ Found CO2 chart label formatting pattern")
        content = re.sub(
            chart_label_pattern,
            'window.historyCO2Chart.data.labels = sorted.map(function(i){ return formatTimestampForChart(i.timestampUnix); });',
            content
        )
    
    # Pattern 2: Similar pattern for pressure chart
    pressure_chart_pattern = r'window\.historyPressureChart\.data\.labels = sorted\.map\(function\(i\)\{ return new Date\(i\.timestampUnix \* 1000\)\.toLocaleString\([^}]+\}\); \}\);'
    
    if re.search(pressure_chart_pattern, content):
        print("✅ Found pressure chart label formatting pattern")
        content = re.sub(
            pressure_chart_pattern,
            'window.historyPressureChart.data.labels = sorted.map(function(i){ return formatTimestampForChart(i.timestampUnix); });',
            content
        )
    
    # Pattern 3: Look for the specific toLocaleString calls in chart updates
    locale_string_pattern = r'new Date\(([^)]+)\)\.toLocaleString\("en-GB", \{timeZone: "Europe/Bucharest", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false\}\)'
    
    matches = re.findall(locale_string_pattern, content)
    if matches:
        print(f"✅ Found {len(matches)} toLocaleString calls to fix")
        # Replace with our helper function call
        content = re.sub(
            locale_string_pattern,
            lambda m: f'formatTimestampForChart({m.group(1)} / 1000)' if '1000' in m.group(1) else f'formatTimestampForChart({m.group(1)})',
            content
        )
    
    # Add the helper function - we need to place it in a good spot
    helper_function = """    // Helper function for consistent timestamp formatting across all charts
    function formatTimestampForChart(timestampUnix) {
      const date = new Date(timestampUnix * 1000);
      
      // Create a more explicit timezone conversion to avoid browser inconsistencies
      const bucharest = new Intl.DateTimeFormat('en-GB', {
        timeZone: 'Europe/Bucharest',
        year: 'numeric',
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      });
      
      return bucharest.format(date);
    }

"""
    
    # Find a good insertion point - before updateDisplay function
    insertion_point = content.find('function updateDisplay()')
    if insertion_point > -1:
        content = content[:insertion_point] + helper_function + content[insertion_point:]
        print("✅ Added formatTimestampForChart helper function")
    else:
        # Try to find another good spot - before any chart update function
        insertion_point = content.find('function updateCO2HistoryChart()')
        if insertion_point > -1:
            content = content[:insertion_point] + helper_function + content[insertion_point:]
            print("✅ Added formatTimestampForChart helper function (alternate location)")
    
    # Check if we made any changes
    if content != original_content:
        print("🔄 Changes detected, applying fixes...")
        
        # Write the fixed content
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Timezone fixes applied successfully!")
        return True
    else:
        print("ℹ️  No changes needed or pattern not found")
        return False

def analyze_current_issue():
    """Analyze the specific issue described by the user"""
    print("🔍 Analyzing current timezone issue...")
    
    frontend_file = '/home/andrei/aMonitoringHub/frontend/index.html'
    
    with open(frontend_file, 'r') as f:
        content = f.read()
    
    # Look for the specific patterns mentioned
    header_timestamp_pattern = r'lastReadingEl\.textContent = \'Last reading time: \' \+ new Date\(latestTimestamp \* 1000\)\.toLocaleString'
    chart_timestamp_pattern = r'sorted\.map\(function\(i\)\{ return new Date\(i\.timestampUnix \* 1000\)\.toLocaleString'
    
    print("📊 Analysis Results:")
    if re.search(header_timestamp_pattern, content):
        print("  ✅ Found header timestamp formatting (shows 18:39 - correct)")
    
    if re.search(chart_timestamp_pattern, content):
        print("  ⚠️  Found chart timestamp formatting (shows 15:39 - 3h off)")
        print("  🎯 This is likely the source of the timezone discrepancy")
    
    # Check timezone specifications
    europe_bucharest_count = len(re.findall(r'Europe/Bucharest', content))
    print(f"  📍 Found {europe_bucharest_count} references to 'Europe/Bucharest' timezone")
    
    return content

def main():
    """Main function"""
    print("🚀 Starting timezone fix for aMonitoringHub")
    print("📋 Issue: Chart shows 15:39 while header shows 18:39 (3-hour difference)\n")
    
    frontend_file = '/home/andrei/aMonitoringHub/frontend/index.html'
    
    if not os.path.exists(frontend_file):
        print(f"❌ Frontend file not found: {frontend_file}")
        return
    
    # Analyze the current issue
    analyze_current_issue()
    print()
    
    # Create backup
    backup_path = backup_file(frontend_file)
    
    try:
        # Apply fixes
        changes_made = fix_timezone_issue(frontend_file)
        
        if changes_made:
            print("\n🎉 Timezone fix completed successfully!")
            print("📝 Summary of changes:")
            print("  ✅ Added formatTimestampForChart() helper function")
            print("  ✅ Replaced chart timestamp formatting with helper function") 
            print("  ✅ Uses explicit Intl.DateTimeFormat for better browser compatibility")
            print(f"\n💾 Original file backed up to: {backup_path}")
            print("\n📋 Next steps:")
            print("  1. Stop the app: ./scripts/app.sh stop")
            print("  2. Start the app: ./scripts/app.sh start")  
            print("  3. Check that both header and chart show the same time")
        else:
            print("\nℹ️  No changes were needed - patterns may have changed")
            # Remove backup if no changes were made
            os.remove(backup_path)
            print("🔍 You may need to manually inspect the chart formatting code")
            
    except Exception as e:
        print(f"❌ Error applying fixes: {e}")
        print("🔄 Restoring from backup...")
        shutil.copy2(backup_path, frontend_file)
        print("✅ Original file restored")

if __name__ == "__main__":
    main()
