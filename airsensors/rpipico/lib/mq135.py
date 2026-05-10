"""
MQ135 Air Quality Sensor Library
Library for reading air quality data from MQ135 sensor via ADC
"""

from machine import Pin, ADC

try:
    from lib.config import (
        MQ135_R_LOAD, MQ135_R_ZERO, MQ135_CO2_A, MQ135_CO2_B,
        MQ135_NH3_A, MQ135_NH3_B, MQ135_ALCOHOL_A, MQ135_ALCOHOL_B,
        MQ135_CO2_MAX, MQ135_NH3_MAX, MQ135_ALCOHOL_MAX,
        ADC_MAX_VALUE, VOLTAGE_REFERENCE, MIN_VOLTAGE_THRESHOLD,
        AQ_EXCELLENT, AQ_GOOD, AQ_FAIR, AQ_POOR, AQ_VERY_POOR,
        VALID_ADC_PINS, MIN_R_ZERO, MAX_R_ZERO, MIN_R_LOAD, MAX_R_LOAD
    )
except ImportError:
    # Fallback defaults if config not available
    MQ135_R_LOAD = 10000
    MQ135_R_ZERO = 42304.5
    MQ135_CO2_A = 116.6020682
    MQ135_CO2_B = -2.769034857
    MQ135_NH3_A = 102.694
    MQ135_NH3_B = -2.815
    MQ135_ALCOHOL_A = 77.255
    MQ135_ALCOHOL_B = -3.18
    MQ135_CO2_MAX = 10000
    MQ135_NH3_MAX = 500
    MQ135_ALCOHOL_MAX = 1000
    ADC_MAX_VALUE = 65535
    VOLTAGE_REFERENCE = 3.3
    MIN_VOLTAGE_THRESHOLD = 0.01
    AQ_EXCELLENT = 400
    AQ_GOOD = 600
    AQ_FAIR = 1000
    AQ_POOR = 1500
    AQ_VERY_POOR = 2500
    VALID_ADC_PINS = list(range(26, 30))
    MIN_R_ZERO = 1000.0
    MAX_R_ZERO = 1000000.0
    MIN_R_LOAD = 100.0
    MAX_R_LOAD = 1000000.0

# Float comparison epsilon
EPSILON = 1e-6

class MQ135:
    def __init__(self, adc_pin, r_zero=None, r_load=None):
        """
        Initialize MQ135 sensor
        
        Args:
            adc_pin: GPIO pin number for ADC input (must be valid ADC pin: 26-29)
            r_zero: Calibrated resistance in clean air (default from config)
            r_load: Load resistor value in ohms (default 10kΩ from config)
        
        Raises:
            ValueError: If pin or resistor values are invalid
        """
        # Validate ADC pin
        if adc_pin not in VALID_ADC_PINS:
            raise ValueError(f"Invalid ADC pin {adc_pin}. Must be one of {VALID_ADC_PINS}")
        
        # Use defaults from config if not provided
        if r_zero is None:
            r_zero = MQ135_R_ZERO
        if r_load is None:
            r_load = MQ135_R_LOAD
        
        # Validate resistor values
        if not (MIN_R_ZERO <= r_zero <= MAX_R_ZERO):
            raise ValueError(f"r_zero ({r_zero}) must be between {MIN_R_ZERO} and {MAX_R_ZERO} ohms")
        if not (MIN_R_LOAD <= r_load <= MAX_R_LOAD):
            raise ValueError(f"r_load ({r_load}) must be between {MIN_R_LOAD} and {MAX_R_LOAD} ohms")
        
        self.adc = ADC(Pin(adc_pin))
        self.r_load = r_load
        self.r_zero = r_zero
        
    def read_voltage(self):
        """Read voltage from ADC"""
        raw = self.adc.read_u16()
        voltage = (raw / ADC_MAX_VALUE) * VOLTAGE_REFERENCE
        return voltage, raw
    
    def read_resistance(self):
        """Calculate sensor resistance"""
        voltage, raw = self.read_voltage()
        # Fix float comparison: use epsilon instead of <= threshold
        if voltage < MIN_VOLTAGE_THRESHOLD + EPSILON:
            return float('inf'), voltage, raw
        resistance = ((VOLTAGE_REFERENCE - voltage) / voltage) * self.r_load
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
        return self._calculate_co2_ppm(ratio), ratio, resistance, voltage, raw
    
    def read_nh3_ppm(self):
        """Estimate NH3 concentration in ppm"""
        ratio, resistance, voltage, raw = self.read_ratio()
        return self._calculate_nh3_ppm(ratio), ratio, resistance, voltage, raw
    
    def read_alcohol_ppm(self):
        """Estimate alcohol concentration in ppm"""
        ratio, resistance, voltage, raw = self.read_ratio()
        return self._calculate_alcohol_ppm(ratio), ratio, resistance, voltage, raw
    
    def get_air_quality_status(self, co2_ppm):
        """
        Get air quality status based on CO2 levels
        
        Returns:
            tuple: (status_string, air_quality_index)
        """
        if co2_ppm < AQ_EXCELLENT:
            return 'Excellent', 1
        elif co2_ppm < AQ_GOOD:
            return 'Good', 2
        elif co2_ppm < AQ_FAIR:
            return 'Fair', 3
        elif co2_ppm < AQ_POOR:
            return 'Poor', 4
        elif co2_ppm < AQ_VERY_POOR:
            return 'Very Poor', 5
        else:
            return 'Hazardous', 6
    
    def get_all_readings(self):
        """Get all sensor readings as a dictionary"""
        ratio, resistance, voltage, raw = self.read_ratio()
        
        co2_ppm = self._calculate_co2_ppm(ratio)
        nh3_ppm = self._calculate_nh3_ppm(ratio)
        alcohol_ppm = self._calculate_alcohol_ppm(ratio)
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
    
    def _calculate_co2_ppm(self, ratio):
        """Calculate CO2 ppm from ratio"""
        if ratio < EPSILON:
            return 0
        ppm = MQ135_CO2_A * (ratio ** MQ135_CO2_B)
        return max(0, min(MQ135_CO2_MAX, ppm))
    
    def _calculate_nh3_ppm(self, ratio):
        """Calculate NH3 ppm from ratio"""
        if ratio < EPSILON:
            return 0
        ppm = MQ135_NH3_A * (ratio ** MQ135_NH3_B)
        return max(0, min(MQ135_NH3_MAX, ppm))
    
    def _calculate_alcohol_ppm(self, ratio):
        """Calculate alcohol ppm from ratio"""
        if ratio < EPSILON:
            return 0
        ppm = MQ135_ALCOHOL_A * (ratio ** MQ135_ALCOHOL_B)
        return max(0, min(MQ135_ALCOHOL_MAX, ppm))

