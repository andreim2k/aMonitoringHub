/**
 * aTemperature Monitor - Lightweight GraphQL + SSE Frontend
 * Real-time temperature monitoring with GraphQL and Server-Sent Events
 */

class TemperatureMonitor {
    constructor() {
        this.eventSource = null;
        this.chart = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.maxChartPoints = 100;
        
        this.elements = {
            status: document.getElementById('status'),
            indicator: document.getElementById('indicator'),
            statusText: document.getElementById('statusText'),
            currentTemp: document.getElementById('currentTemp'),
            sensorInfo: document.getElementById('sensorInfo'),
            lastUpdate: document.getElementById('lastUpdate'),
            avgTemp: document.getElementById('avgTemp'),
            minTemp: document.getElementById('minTemp'),
            maxTemp: document.getElementById('maxTemp'),
            readingCount: document.getElementById('readingCount'),
            timeRange: document.getElementById('timeRange'),
            refreshBtn: document.getElementById('refreshBtn'),
            chart: document.getElementById('temperatureChart')
        };
        
        this.init();
    }
    
    init() {
        console.log('Initializing Temperature Monitor with GraphQL + SSE...');
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Initialize chart
        this.initChart();
        
        // Connect to Server-Sent Events
        this.connectSSE();
        
        // Load initial data via GraphQL
        this.loadInitialData();
    }
    
    setupEventListeners() {
        // Refresh button
        this.elements.refreshBtn.addEventListener('click', () => {
            this.loadHistoricalData();
        });
        
        // Time range selector
        this.elements.timeRange.addEventListener('change', () => {
            this.loadHistoricalData();
        });
        
        // Page visibility API for auto-reconnection
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && 
                (!this.eventSource || this.eventSource.readyState === EventSource.CLOSED)) {
                this.connectSSE();
            }
        });
    }
    
    initChart() {
        const ctx = this.elements.chart.getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleColor: 'white',
                        bodyColor: 'white',
                        callbacks: {
                            label: function(context) {
                                return `Temperature: ${context.parsed.y.toFixed(2)}°C`;
                            },
                            title: function(context) {
                                const date = new Date(context[0].parsed.x);
                                return date.toLocaleString();
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            displayFormats: {
                                minute: 'HH:mm',
                                hour: 'HH:mm',
                                day: 'MM/DD'
                            }
                        },
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: 'Temperature (°C)'
                        },
                        beginAtZero: false
                    }
                },
                animation: {
                    duration: 300
                }
            }
        });
    }
    
    // GraphQL Query Helper
    async graphqlQuery(query, variables = {}) {
        try {
            const response = await fetch('/graphql', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query, variables })
            });
            
            const result = await response.json();
            
            if (result.errors) {
                console.error('GraphQL errors:', result.errors);
                return null;
            }
            
            return result.data;
        } catch (error) {
            console.error('GraphQL request failed:', error);
            return null;
        }
    }
    
    // Server-Sent Events Connection
    connectSSE() {
        console.log('Connecting to Server-Sent Events...');
        
        if (this.eventSource) {
            this.eventSource.close();
        }
        
        this.eventSource = new EventSource('/events');
        
        this.eventSource.onopen = () => {
            console.log('SSE connected');
            this.updateStatus('connected', 'Connected');
            this.reconnectAttempts = 0;
        };
        
        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                
                if (data.type === 'temperature_update') {
                    console.log('Temperature update received:', data.data);
                    this.updateTemperatureDisplay(data.data);
                    this.addTemperatureToChart(data.data);
                } else if (data.type === 'heartbeat') {
                    console.log('Heartbeat received');
                }
            } catch (error) {
                console.error('Error parsing SSE message:', error);
            }
        };
        
        this.eventSource.onerror = () => {
            console.log('SSE connection error');
            this.updateStatus('error', 'Disconnected');
            this.scheduleReconnect();
        };
    }
    
    scheduleReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Scheduling SSE reconnect attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`);
            
            setTimeout(() => {
                this.updateStatus('connecting', `Reconnecting... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                this.connectSSE();
            }, this.reconnectDelay);
        } else {
            this.updateStatus('error', 'Connection Failed - Reload page to retry');
        }
    }
    
    updateStatus(status, text) {
        this.elements.indicator.className = `indicator ${status}`;
        this.elements.statusText.textContent = text;
    }
    
    updateTemperatureDisplay(data) {
        // Update current temperature with animation
        this.elements.currentTemp.classList.add('updated');
        this.elements.currentTemp.textContent = data.temperature_c.toFixed(1);
        
        // Remove animation class after animation completes
        setTimeout(() => {
            this.elements.currentTemp.classList.remove('updated');
        }, 500);
        
        // Update sensor info and timestamp
        this.elements.sensorInfo.textContent = `Sensor: ${data.sensor_id} (${data.sensor_type})`;
        this.elements.lastUpdate.textContent = `Last update: ${new Date(data.timestamp_iso).toLocaleTimeString()}`;
    }
    
    addTemperatureToChart(data) {
        const timestamp = new Date(data.timestamp_iso);
        const temperature = data.temperature_c;
        
        // Add new data point
        this.chart.data.labels.push(timestamp);
        this.chart.data.datasets[0].data.push({
            x: timestamp,
            y: temperature
        });
        
        // Keep only recent points for real-time view
        if (this.chart.data.labels.length > this.maxChartPoints) {
            this.chart.data.labels.shift();
            this.chart.data.datasets[0].data.shift();
        }
        
        this.chart.update('none'); // Update without animation for real-time
    }
    
    // Load initial data using GraphQL
    async loadInitialData() {
        // Load current temperature and sensor info
        await this.loadCurrentTemperature();
        
        // Load statistics
        await this.loadStatistics();
        
        // Load historical data
        await this.loadHistoricalData();
    }
    
    async loadCurrentTemperature() {
        const query = `
            query {
                currentTemperature {
                    temperatureC
                    timestamp
                    timestampUnix
                    sensorType
                    sensorId
                }
                sensorInfo {
                    sensorType
                    sensorId
                    initialized
                }
            }
        `;
        
        const data = await this.graphqlQuery(query);
        
        if (data && data.currentTemperature) {
            const temp = data.currentTemperature;
            this.elements.currentTemp.textContent = temp.temperatureC.toFixed(1);
            this.elements.lastUpdate.textContent = `Last update: ${new Date(temp.timestamp).toLocaleTimeString()}`;
        }
        
        if (data && data.sensorInfo) {
            const sensor = data.sensorInfo;
            this.elements.sensorInfo.textContent = `Sensor: ${sensor.sensorId} (${sensor.sensorType})`;
        }
    }
    
    async loadStatistics() {
        const query = `
            query {
                temperatureStatistics(hours: 24) {
                    count
                    average
                    minimum
                    maximum
                }
            }
        `;
        
        const data = await this.graphqlQuery(query);
        
        if (data && data.temperatureStatistics) {
            const stats = data.temperatureStatistics;
            this.elements.avgTemp.textContent = `${stats.average.toFixed(1)}°C`;
            this.elements.minTemp.textContent = `${stats.minimum.toFixed(1)}°C`;
            this.elements.maxTemp.textContent = `${stats.maximum.toFixed(1)}°C`;
            this.elements.readingCount.textContent = stats.count;
        }
    }
    
    async loadHistoricalData() {
        try {
            const range = this.elements.timeRange.value;
            console.log('Loading historical data for range:', range);
            
            this.elements.refreshBtn.classList.add('loading');
            this.elements.refreshBtn.textContent = 'Loading...';
            
            const query = `
                query GetTemperatureHistory($range: String, $limit: Int) {
                    temperatureHistory(range: $range, limit: $limit) {
                        temperatureC
                        timestamp
                        timestampUnix
                        sensorType
                        sensorId
                    }
                }
            `;
            
            const data = await this.graphqlQuery(query, { range, limit: 1000 });
            
            if (data && data.temperatureHistory) {
                this.updateChart(data.temperatureHistory);
                console.log(`Loaded ${data.temperatureHistory.length} historical readings`);
            } else {
                throw new Error('No data received from GraphQL');
            }
            
        } catch (error) {
            console.error('Error loading historical data:', error);
            this.updateStatus('error', 'Failed to load data');
        } finally {
            this.elements.refreshBtn.classList.remove('loading');
            this.elements.refreshBtn.textContent = 'Refresh Chart';
        }
    }
    
    updateChart(readings) {
        const labels = [];
        const temperatures = [];
        
        readings.forEach(reading => {
            const timestamp = new Date(reading.timestamp);
            labels.push(timestamp);
            temperatures.push({
                x: timestamp,
                y: reading.temperatureC
            });
        });
        
        this.chart.data.labels = labels;
        this.chart.data.datasets[0].data = temperatures;
        this.chart.update();
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Check if required dependencies are loaded
    if (typeof Chart === 'undefined') {
        console.error('Chart.js not loaded');
        document.body.innerHTML = '<div style="text-align: center; padding: 50px; color: red;">Error: Chart.js failed to load. Please check your internet connection.</div>';
        return;
    }
    
    console.log('Starting aTemperature Monitor with GraphQL + SSE');
    
    // Initialize the temperature monitor
    window.temperatureMonitor = new TemperatureMonitor();
});

// Add some helper functions for debugging
window.testGraphQL = async function(query) {
    const monitor = window.temperatureMonitor;
    if (monitor) {
        const result = await monitor.graphqlQuery(query);
        console.log('GraphQL Result:', result);
        return result;
    }
};

// Example usage: testGraphQL('{ health { status timestamp } }')
