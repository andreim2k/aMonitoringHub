"""
MQ135 Air Quality Sensor Library
Library for reading air quality data from MQ135 sensor via ADC
"""

from machine import Pin, ADC

# Float comparison epsilon
EPSILON = 1e-6

class MQ135:
    def __init__(self, adc_pin, r_zero=42304.5, r_load=10000):
        """
        Initialize MQ135 sensor
        
        Args:
            adc_pin: GPIO pin number for ADC input
            r_zero: Calibrated resistance in clean air (default from config)
            r_load: Load resistor value in ohms (default 10kΩ)
        """
        self.adc = ADC(Pin(adc_pin))
        self.r_load = r_load
        self.r_zero = r_zero
        
    def read_voltage(self):
        """Read voltage from ADC"""
        raw = self.adc.read_u16()
        voltage = (raw / 65535) * 3.3
        return voltage, raw
    
    def read_resistance(self):
        """Calculate sensor resistance"""
        voltage, raw = self.read_voltage()
        # Fix float comparison: use epsilon instead of <= 0.01
        if voltage < 0.01 + EPSILON:
            return float('inf'), voltage, raw
        resistance = ((3.3 - voltage) / voltage) * self.r_load
        return resistance, voltage, raw
    
    def read_ratio(self):
        """Read Rs/R0 ratio"""
        resistance, voltage, raw = self.read_resistance()
        # Fix float comparison: check for infinity and zero with epsilon
        if resistance == float('inf') or abs(self.r_zero) < EPSILON:
            return 0, resistance, voltage, raw
        ratio = resistance / self.r_zero
        return ratio, resistance, voltage, raw
    
    def read_co2_ppm(self):
        """Estimate CO2 concentration in ppm"""
        ratio, resistance, voltage, raw = self.read_ratio()
        # Fix float comparison: use epsilon
        if ratio < EPSILON:
            return 0, ratio, resistance, voltage, raw
        ppm = 116.6020682 * (ratio ** -2.769034857)
        return max(0, min(10000, ppm)), ratio, resistance, voltage, raw
    
    def read_nh3_ppm(self):
        """Estimate NH3 concentration in ppm"""
        ratio, resistance, voltage, raw = self.read_ratio()
        # Fix float comparison: use epsilon
        if ratio < EPSILON:
            return 0, ratio, resistance, voltage, raw
        ppm = 102.694 * (ratio ** -2.815)
        return max(0, min(500, ppm)), ratio, resistance, voltage, raw
    
    def read_alcohol_ppm(self):
        """Estimate alcohol concentration in ppm"""
        ratio, resistance, voltage, raw = self.read_ratio()
        # Fix float comparison: use epsilon
        if ratio < EPSILON:
            return 0, ratio, resistance, voltage, raw
        ppm = 77.255 * (ratio ** -3.18)
        return max(0, min(1000, ppm)), ratio, resistance, voltage, raw
    
    def get_air_quality_status(self, co2_ppm):
        """
        Get air quality status based on CO2 levels
        
        Returns:
            tuple: (status_string, air_quality_index)
        """
        if co2_ppm < 400:
            return 'Excellent', 1
        elif co2_ppm < 600:
            return 'Good', 2
        elif co2_ppm < 1000:
            return 'Fair', 3
        elif co2_ppm < 1500:
            return 'Poor', 4
        elif co2_ppm < 2500:
            return 'Very Poor', 5
        else:
            return 'Hazardous', 6
    
    def get_all_readings(self):
        """Get all sensor readings as a dictionary"""
        co2_ppm, ratio, resistance, voltage, raw = self.read_co2_ppm()
        nh3_ppm, _, _, _, _ = self.read_nh3_ppm()
        alcohol_ppm, _, _, _, _ = self.read_alcohol_ppm()
        status, aqi = self.get_air_quality_status(co2_ppm)
        
        return {
            'raw_adc': raw,
            'voltage_v': round(voltage, 3),
            'resistance_ohm': round(resistance, 1),
            'ratio_rs_r0': round(ratio, 3),
            'co2_ppm': round(co2_ppm, 1),
            'nh3_ppm': round(nh3_ppm, 1),
            'alcohol_ppm': round(alcohol_ppm, 1),
            'air_quality_status': status,
            'air_quality_index': aqi,
            'r_zero_ohm': self.r_zero
        }

