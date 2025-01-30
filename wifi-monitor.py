import speedtest
import time
from datetime import datetime, timedelta
import pandas as pd
import csv
from pathlib import Path
import logging
import socket
from statistics import mean, stdev
from collections import defaultdict

class WiFiMonitor:
    def __init__(self):
        self.speeds = []
        self.disconnections = []
        self.hourly_averages = {}
        self.current_hour = datetime.now().hour
        self.speed_extremes = {
            'max_download': {'speed': 0, 'timestamp': None},
            'min_download': {'speed': float('inf'), 'timestamp': None},
            'max_upload': {'speed': 0, 'timestamp': None},
            'min_upload': {'speed': float('inf'), 'timestamp': None}
        }
        self.setup_logging()
        
    def setup_logging(self):
        logging.basicConfig(
            filename='wifi_monitor.log',
            level=logging.INFO,
            format='%(asctime)s - %(message)s'
        )
    
    def check_connection(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False
    
    def measure_speed(self):
        try:
            st = speedtest.Speedtest()
            st.get_best_server()
            download_speed = st.download() / 1_000_000  # Convert to Mbps
            upload_speed = st.upload() / 1_000_000  # Convert to Mbps
            self.update_speed_extremes(download_speed, upload_speed)
            return download_speed, upload_speed
        except Exception as e:
            logging.error(f"Speed test failed: {str(e)}")
            return None, None
    
    def update_speed_extremes(self, download_speed, upload_speed):
        current_time = datetime.now()
        
        if download_speed > self.speed_extremes['max_download']['speed']:
            self.speed_extremes['max_download'] = {
                'speed': download_speed,
                'timestamp': current_time
            }
        if download_speed < self.speed_extremes['min_download']['speed']:
            self.speed_extremes['min_download'] = {
                'speed': download_speed,
                'timestamp': current_time
            }
            
        if upload_speed > self.speed_extremes['max_upload']['speed']:
            self.speed_extremes['max_upload'] = {
                'speed': upload_speed,
                'timestamp': current_time
            }
        if upload_speed < self.speed_extremes['min_upload']['speed']:
            self.speed_extremes['min_upload'] = {
                'speed': upload_speed,
                'timestamp': current_time
            }
    
    def track_disconnection(self, start_time):
        while not self.check_connection():
            time.sleep(5)  # Check every 5 seconds
        end_time = datetime.now()
        duration = end_time - start_time
        self.disconnections.append({
            'start': start_time,
            'end': end_time,
            'duration': duration
        })
        logging.info(f"Connection restored after {duration}")

    def analyze_patterns(self):
        if not self.speeds:
            return None

        # Convert speeds to pandas DataFrame for analysis
        df = pd.DataFrame(self.speeds)
        
        # Analyze hourly patterns
        hourly_patterns = df.groupby(df['timestamp'].dt.hour).agg({
            'download': ['mean', 'std'],
            'upload': ['mean', 'std']
        })
        
        # Identify peak and low usage hours
        peak_hours = {
            'download': hourly_patterns['download']['mean'].idxmax(),
            'upload': hourly_patterns['upload']['mean'].idxmax()
        }
        
        low_hours = {
            'download': hourly_patterns['download']['mean'].idxmin(),
            'upload': hourly_patterns['upload']['mean'].idxmin()
        }
        
        # Calculate stability scores (lower std dev means more stable)
        stability = {
            'download': hourly_patterns['download']['std'].mean(),
            'upload': hourly_patterns['upload']['std'].mean()
        }
        
        return {
            'peak_hours': peak_hours,
            'low_hours': low_hours,
            'stability': stability,
            'hourly_patterns': hourly_patterns
        }

    def calculate_total_downtime(self):
        total_duration = timedelta()
        for d in self.disconnections:
            total_duration += d['duration']
        return total_duration
    
    def generate_report(self, filename="wifi_report.txt"):
        patterns = self.analyze_patterns()
        total_downtime = self.calculate_total_downtime()
        
        # Create report content
        report_content = []
        
        # Add report header
        report_content.append("=" * 30 + " WiFi Monitoring Report " + "=" * 30)
        report_content.append(f"Report generated at: {datetime.now()}\n")
        
        # Speed Extremes Section
        report_content.append("=" * 30 + " Speed Extremes " + "=" * 30)
        report_content.append(f"Maximum Download: {self.speed_extremes['max_download']['speed']:.2f} Mbps " +
                               f"at {self.speed_extremes['max_download']['timestamp']}")
        report_content.append(f"Minimum Download: {self.speed_extremes['min_download']['speed']:.2f} Mbps " +
                               f"at {self.speed_extremes['min_download']['timestamp']}")
        report_content.append(f"Maximum Upload: {self.speed_extremes['max_upload']['speed']:.2f} Mbps " +
                               f"at {self.speed_extremes['max_upload']['timestamp']}")
        report_content.append(f"Minimum Upload: {self.speed_extremes['min_upload']['speed']:.2f} Mbps " +
                               f"at {self.speed_extremes['min_upload']['timestamp']}\n")
        
        # Connection Issues Section
        report_content.append("=" * 30 + " Connection Summary " + "=" * 30)
        report_content.append(f"Total Disconnection Time: {total_downtime}")
        report_content.append(f"Number of Disconnections: {len(self.disconnections)}\n")
        
        # Detailed Disconnections
        report_content.append("=" * 30 + " Detailed Disconnections " + "=" * 30)
        if self.disconnections:
            for d in self.disconnections:
                report_content.append(f"Disconnected at: {d['start']}")
                report_content.append(f"Reconnected at: {d['end']}")
                report_content.append(f"Duration: {d['duration']}\n")
        else:
            report_content.append("No disconnections recorded\n")
        
        # Pattern Analysis
        if patterns:
            report_content.append("=" * 30 + " Speed Patterns " + "=" * 30)
            report_content.append(f"Peak Download Speed Hour: {patterns['peak_hours']['download']:02d}:00")
            report_content.append(f"Peak Upload Speed Hour: {patterns['peak_hours']['upload']:02d}:00")
            report_content.append(f"Lowest Download Speed Hour: {patterns['low_hours']['download']:02d}:00")
            report_content.append(f"Lowest Upload Speed Hour: {patterns['low_hours']['upload']:02d}:00")
            report_content.append("\nConnection Stability (lower is better):")
            report_content.append(f"Download Stability Score: {patterns['stability']['download']:.2f}")
            report_content.append(f"Upload Stability Score: {patterns['stability']['upload']:.2f}\n")
        
        # Hourly Averages
        report_content.append("=" * 30 + " Hourly Speed Averages " + "=" * 30)
        for hour, data in sorted(self.hourly_averages.items()):
            report_content.append(f"\nHour {hour:02d}:00")
            report_content.append(f"Average Download: {data['download']:.2f} Mbps")
            report_content.append(f"Average Upload: {data['upload']:.2f} Mbps")
            report_content.append(f"Samples taken: {data['samples']}")
        
        # Print report to terminal
        print("\n".join(report_content))
        
        # Write report to file
        with open(filename, 'w') as f:
            f.write("\n".join(report_content))
        
        logging.info("Report generated and saved to " + filename)

    def calculate_hourly_average(self):
        """
        Calculate average speeds for the current hour and store in hourly_averages.
        """
        if not self.speeds:
            return

        # Filter speeds for the current hour
        hour_speeds = [
            speed for speed in self.speeds 
            if speed['hour'] == self.current_hour
        ]

        if not hour_speeds:
            return

        # Calculate averages
        download_speeds = [speed['download'] for speed in hour_speeds]
        upload_speeds = [speed['upload'] for speed in hour_speeds]

        self.hourly_averages[self.current_hour] = {
            'download': mean(download_speeds),
            'upload': mean(upload_speeds),
            'samples': len(hour_speeds)
        }
        
    def run(self, duration_hours=1/6):
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)
        
        logging.info(f"Starting WiFi monitoring at {start_time}")
        
        while datetime.now() < end_time:
            current_time = datetime.now()
            
            # Check if hour has changed
            if current_time.hour != self.current_hour:
                self.calculate_hourly_average()
                self.current_hour = current_time.hour
            
            # Check connection
            if not self.check_connection():
                disconnect_time = datetime.now()
                logging.warning(f"Connection lost at {disconnect_time}")
                self.track_disconnection(disconnect_time)
                continue
            
            # Measure speed
            download_speed, upload_speed = self.measure_speed()
            if download_speed and upload_speed:
                self.speeds.append({
                    'timestamp': current_time,
                    'hour': current_time.hour,
                    'download': download_speed,
                    'upload': upload_speed
                })
                logging.info(f"Speed test: Download={download_speed:.2f} Mbps, Upload={upload_speed:.2f} Mbps")
            
            # Wait for the next measurement
            time.sleep(60)  # Test every minute
        
        # Generate final report
        self.calculate_hourly_average()  # Calculate average for the last hour
        self.generate_report()
        logging.info("Monitoring completed. Report generated.")

if __name__ == "__main__":
    monitor = WiFiMonitor()
    monitor.run()