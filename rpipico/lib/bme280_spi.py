"""
BME280 SPI driver for MicroPython on RP2040.

Designed for long-running stability:
- No post-success "timeout" check that converted slow reads into spurious failures.
- No data-ready polling in normal mode (the data registers always hold the last
  conversion; polling the status bits was both wrong and unnecessary).
- Pre-allocated tx/rx buffers, so steady-state reads do not allocate.
"""

import time

try:
    from lib.config import (
        BME280_CHIP_ID_REG,
        BME280_RESET_REG, BME280_RESET_VALUE,
        BME280_CTRL_HUM_REG, BME280_CTRL_HUM_VALUE,
        BME280_STATUS_REG,
        BME280_CTRL_MEAS_REG, BME280_CTRL_MEAS_VALUE,
        BME280_CONFIG_REG, BME280_CONFIG_VALUE,
        BME280_DATA_REG,
        SPI_OP_RETRIES, SPI_RETRY_DELAY_MS,
    )
except ImportError:
    BME280_CHIP_ID_REG = 0xD0
    BME280_RESET_REG = 0xE0
    BME280_RESET_VALUE = 0xB6
    BME280_CTRL_HUM_REG = 0xF2
    BME280_CTRL_HUM_VALUE = 0x01
    BME280_STATUS_REG = 0xF3
    BME280_CTRL_MEAS_REG = 0xF4
    BME280_CTRL_MEAS_VALUE = 0x27
    BME280_CONFIG_REG = 0xF5
    BME280_CONFIG_VALUE = 0x20
    BME280_DATA_REG = 0xF7
    SPI_OP_RETRIES = 3
    SPI_RETRY_DELAY_MS = 10

EPSILON = 1e-6
_MAX_BURST = 26  # largest burst we ever do is 24 (calibration)


class BME280_SPI:
    def __init__(self, spi, cs_pin):
        if spi is None:
            raise ValueError("SPI bus object cannot be None")
        if cs_pin is None:
            raise ValueError("CS pin object cannot be None")

        self.spi = spi
        self.cs = cs_pin
        self.cs.on()  # deselect

        # Pre-allocate buffers reused for every SPI transfer.
        self._tx = bytearray(_MAX_BURST + 1)
        self._rx = bytearray(_MAX_BURST + 1)

        chip_id = self._read_register(BME280_CHIP_ID_REG)
        if chip_id not in (0x60, 0x58):
            raise ValueError("Invalid chip ID: 0x%02X" % chip_id)
        self.chip_id = chip_id
        self.has_humidity = (chip_id == 0x60)

        self.reset()
        time.sleep(0.05)  # NVM copy after reset
        self._read_calibration_data()
        self._configure_sensor()

    # ---- low-level SPI ----

    def _read_register(self, reg):
        last_error = None
        for attempt in range(SPI_OP_RETRIES):
            try:
                self._tx[0] = reg | 0x80
                self._tx[1] = 0xFF
                self.cs.off()
                try:
                    self.spi.write_readinto(memoryview(self._tx)[:2],
                                            memoryview(self._rx)[:2])
                finally:
                    self.cs.on()
                return self._rx[1]
            except (OSError, ValueError) as e:
                self.cs.on()
                last_error = e
                if attempt < SPI_OP_RETRIES - 1:
                    time.sleep_ms(SPI_RETRY_DELAY_MS)
        raise last_error

    def _read_registers(self, reg, count):
        if count + 1 > len(self._tx):
            # Grow only if some odd caller asks for more (should not happen).
            self._tx = bytearray(count + 1)
            self._rx = bytearray(count + 1)
        last_error = None
        for attempt in range(SPI_OP_RETRIES):
            try:
                self._tx[0] = reg | 0x80
                for i in range(1, count + 1):
                    self._tx[i] = 0xFF
                tx = memoryview(self._tx)[:count + 1]
                rx = memoryview(self._rx)[:count + 1]
                self.cs.off()
                try:
                    self.spi.write_readinto(tx, rx)
                finally:
                    self.cs.on()
                # Return a fresh bytes copy so the caller's view is stable
                # across subsequent SPI ops that reuse self._rx.
                return bytes(memoryview(self._rx)[1:count + 1])
            except (OSError, ValueError) as e:
                self.cs.on()
                last_error = e
                if attempt < SPI_OP_RETRIES - 1:
                    time.sleep_ms(SPI_RETRY_DELAY_MS)
        raise last_error

    def _write_register(self, reg, value):
        last_error = None
        for attempt in range(SPI_OP_RETRIES):
            try:
                self._tx[0] = reg & 0x7F
                self._tx[1] = value & 0xFF
                self.cs.off()
                try:
                    self.spi.write(memoryview(self._tx)[:2])
                finally:
                    self.cs.on()
                return
            except (OSError, ValueError) as e:
                self.cs.on()
                last_error = e
                if attempt < SPI_OP_RETRIES - 1:
                    time.sleep_ms(SPI_RETRY_DELAY_MS)
        raise last_error

    # ---- calibration / config ----

    @staticmethod
    def _to_signed(value, bits):
        if value & (1 << (bits - 1)):
            return value - (1 << bits)
        return value

    def _read_calibration_data(self):
        c = self._read_registers(0x88, 24)
        self.dig_T1 = c[1] << 8 | c[0]
        self.dig_T2 = self._to_signed(c[3] << 8 | c[2], 16)
        self.dig_T3 = self._to_signed(c[5] << 8 | c[4], 16)
        self.dig_P1 = c[7] << 8 | c[6]
        self.dig_P2 = self._to_signed(c[9] << 8 | c[8], 16)
        self.dig_P3 = self._to_signed(c[11] << 8 | c[10], 16)
        self.dig_P4 = self._to_signed(c[13] << 8 | c[12], 16)
        self.dig_P5 = self._to_signed(c[15] << 8 | c[14], 16)
        self.dig_P6 = self._to_signed(c[17] << 8 | c[16], 16)
        self.dig_P7 = self._to_signed(c[19] << 8 | c[18], 16)
        self.dig_P8 = self._to_signed(c[21] << 8 | c[20], 16)
        self.dig_P9 = self._to_signed(c[23] << 8 | c[22], 16)

        if self.has_humidity:
            self.dig_H1 = self._read_register(0xA1)
            c2 = self._read_registers(0xE1, 7)
            self.dig_H2 = self._to_signed(c2[1] << 8 | c2[0], 16)
            self.dig_H3 = c2[2]
            self.dig_H4 = self._to_signed(c2[3] << 4 | (c2[4] & 0x0F), 12)
            self.dig_H5 = self._to_signed((c2[5] << 4) | (c2[4] >> 4), 12)
            self.dig_H6 = self._to_signed(c2[6], 8)

    def _configure_sensor(self):
        # Humidity must be written before ctrl_meas to take effect.
        if self.has_humidity:
            self._write_register(BME280_CTRL_HUM_REG, BME280_CTRL_HUM_VALUE)
        self._write_register(BME280_CTRL_MEAS_REG, BME280_CTRL_MEAS_VALUE)
        self._write_register(BME280_CONFIG_REG, BME280_CONFIG_VALUE)

    # ---- public API ----

    def reset(self):
        self._write_register(BME280_RESET_REG, BME280_RESET_VALUE)
        time.sleep_ms(10)

    def check_status(self):
        return self._read_register(BME280_STATUS_REG)

    def read_raw_data(self):
        # Normal mode: data registers always hold the latest conversion.
        # No status polling — that gate was the source of long-run failures.
        n = 8 if self.has_humidity else 6
        data = self._read_registers(BME280_DATA_REG, n)
        raw_press = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        raw_temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        raw_hum = (data[6] << 8) | data[7] if self.has_humidity else 0
        return raw_temp, raw_press, raw_hum

    def read_compensated_data(self):
        raw_temp, raw_press, raw_hum = self.read_raw_data()

        var1 = (raw_temp / 16384.0 - self.dig_T1 / 1024.0) * self.dig_T2
        var2 = ((raw_temp / 131072.0 - self.dig_T1 / 8192.0) *
                (raw_temp / 131072.0 - self.dig_T1 / 8192.0)) * self.dig_T3
        t_fine = int(var1 + var2)
        temperature = (var1 + var2) / 5120.0

        var1 = (t_fine / 2.0) - 64000.0
        var2 = var1 * var1 * self.dig_P6 / 32768.0
        var2 = var2 + var1 * self.dig_P5 * 2.0
        var2 = (var2 / 4.0) + (self.dig_P4 * 65536.0)
        var1 = (self.dig_P3 * var1 * var1 / 524288.0 + self.dig_P2 * var1) / 524288.0
        var1 = (1.0 + var1 / 32768.0) * self.dig_P1

        if abs(var1) < EPSILON:
            pressure = 0
        else:
            pressure = 1048576.0 - raw_press
            pressure = (pressure - (var2 / 4096.0)) * 6250.0 / var1
            var1 = self.dig_P9 * pressure * pressure / 2147483648.0
            var2 = pressure * self.dig_P8 / 32768.0
            pressure = pressure + (var1 + var2 + self.dig_P7) / 16.0

        if self.has_humidity:
            h = t_fine - 76800.0
            h = ((raw_hum - (self.dig_H4 * 64.0 + self.dig_H5 / 16384.0 * h)) *
                 (self.dig_H2 / 65536.0 * (1.0 + self.dig_H6 / 67108864.0 * h *
                  (1.0 + self.dig_H3 / 67108864.0 * h))))
            humidity = h * (1.0 - self.dig_H1 * h / 524288.0)
            if humidity > 100:
                humidity = 100
            elif humidity < 0:
                humidity = 0
        else:
            humidity = 0

        return temperature, pressure, humidity
