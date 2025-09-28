#!/usr/bin/env python3
"""
Enhanced Timezone Fix Script for aMonitoringHub
Fixes chart data not refreshing and ensures proper timezone display
"""

import re
import shutil
import os
from datetime import datetime

def backup_file(filepath):
    """Create a backup of the original file"""
    backup_path = f"{filepath}.backup_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path

def force_chart_refresh(filepath):
    """Add code to force chart refresh and clear cached labels"""
    
    print("🔄 Adding chart refresh logic...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # Find the chart update functions and add chart destruction/recreation
    # This will force the charts to refresh with new timestamp formatting
    
    # Enhanced CO2 chart update function
    co2_update_pattern = r'(function updateCO2HistoryChart\(\) \{[^}]+\})'
    
    enhanced_co2_function = """function updateCO2HistoryChart() {
      if (!window.historyCO2Chart || !window.historyCO2Chart.data || currentData.airQualityHistory.length === 0) return;
      
      // Destroy existing chart to force refresh
      if (window.historyCO2Chart) {
        window.historyCO2Chart.destroy();
        window.historyCO2Chart = null;
      }
      
      const sorted = currentData.airQualityHistory.slice().sort(function(a,b){ return a.timestampUnix - b.timestampUnix; });
      
      // Recreate chart with fresh data and correct timestamps
      const ctx = document.getElementById('co2HistoryChart');
      if (ctx) {
        window.historyCO2Chart = new Chart(ctx.getContext('2d'), {
          type: 'line',
          data: {
            labels: sorted.map(function(i){ return formatTimestampForChart(i.timestampUnix); }),
            datasets: [{
              label: 'CO2 (ppm)',
              data: sorted.map(function(i){ return i.co2Ppm; }),
              borderColor: '#ff6b6b',
              backgroundColor: 'rgba(255, 107, 107, 0.1)',
              fill: true,
              tension: 0.1
            }]
          },
          options: {
            responsive: true,
            scales: {
              y: { beginAtZero: false },
              x: { 
                ticks: {
                  maxTicksLimit: 8,
                  callback: function(value, index, values) {
                    // Ensure x-axis labels are also using our timezone function
                    return this.getLabelForValue(value);
                  }
                }
              }
            },
            plugins: {
              legend: { display: true }
            }
          }
        });
      }
    }"""
    
    # Replace the CO2 chart update function
    if re.search(co2_update_pattern, content, re.DOTALL):
        content = re.sub(co2_update_pattern, enhanced_co2_function, content, flags=re.DOTALL)
        print("✅ Enhanced updateCO2HistoryChart function")
    
    # Also enhance the pressure chart update function
    pressure_update_pattern = r'(function updatePressureHistoryChart\(\) \{[^}]+\})'
    
    enhanced_pressure_function = """function updatePressureHistoryChart() {
      if (!window.historyPressureChart || !window.historyPressureChart.data || currentData.pressureHistory.length === 0) return;
      
      // Clear existing data and refresh with correct timestamps
      const sorted = currentData.pressureHistory.slice().sort(function(a,b){ return a.timestampUnix - b.timestampUnix; });
      window.historyPressureChart.data.labels = sorted.map(function(i){ return formatTimestampForChart(i.timestampUnix); });
      window.historyPressureChart.data.datasets[0].data = sorted.map(function(i){ return i.pressureHpa; });
      window.historyPressureChart.update('active');
    }"""
    
    if re.search(pressure_update_pattern, content, re.DOTALL):
        content = re.sub(pressure_update_pattern, enhanced_pressure_function, content, flags=re.DOTALL)
        print("✅ Enhanced updatePressureHistoryChart function")
    
    # Add a function to refresh all charts
    refresh_all_charts_function = """
    // Function to refresh all charts with correct timezone
    function refreshAllChartsTimezone() {
      console.log('🕐 Refreshing all charts with correct timezone...');
      
      // Force update all chart functions
      if (typeof updateCO2HistoryChart === 'function') {
        updateCO2HistoryChart();
      }
      if (typeof updatePressureHistoryChart === 'function') {
        updatePressureHistoryChart(); 
      }
      if (typeof updateHumidityHistoryChart === 'function') {
        updateHumidityHistoryChart();
      }
      
      console.log('✅ All charts refreshed');
    }

"""
    
    # Add this function before the updateDisplay function
    insertion_point = content.find('function updateDisplay()')
    if insertion_point > -1:
        content = content[:insertion_point] + refresh_all_charts_function + content[insertion_point:]
        print("✅ Added refreshAllChartsTimezone function")
    
    # Add a call to refresh charts after data loading
    # Find where air quality history is loaded and add refresh call
    aq_history_pattern = r'(updateCO2HistoryChart\(\);)'
    content = re.sub(aq_history_pattern, r'\1\n          refreshAllChartsTimezone();', content)
    
    return content if content != original_content else None

def main():
    """Main function"""
    print("🚀 Enhanced timezone fix for aMonitoringHub v2")
    print("📋 Issue: Charts still showing old timestamps despite fix")
    
    frontend_file = '/home/andrei/aMonitoringHub/frontend/index.html'
    
    if not os.path.exists(frontend_file):
        print(f"❌ Frontend file not found: {frontend_file}")
        return
    
    # Create backup
    backup_path = backup_file(frontend_file)
    
    try:
        # Apply enhanced fixes
        new_content = force_chart_refresh(frontend_file)
        
        if new_content:
            with open(frontend_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("\n🎉 Enhanced timezone fix completed!")
            print("📝 Changes applied:")
            print("  ✅ Enhanced chart update functions to force refresh")
            print("  ✅ Added chart destruction and recreation for CO2 chart")
            print("  ✅ Added refreshAllChartsTimezone() function")
            print("  ✅ Force chart refresh after data loading")
            print(f"\n💾 Original file backed up to: {backup_path}")
            
            return True
        else:
            print("\nℹ️  No additional changes were needed")
            os.remove(backup_path)
            return False
            
    except Exception as e:
        print(f"❌ Error applying enhanced fixes: {e}")
        print("🔄 Restoring from backup...")
        shutil.copy2(backup_path, frontend_file)
        print("✅ Original file restored")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n📋 Next steps:")
        print("  1. Restart the app: ./scripts/app.sh restart")
        print("  2. Hard refresh browser (Ctrl+F5) to clear cache")
        print("  3. Check that chart now shows correct timestamps")
        print("  4. Open browser console to see 'Refreshing all charts' message")
