#!/usr/bin/env python3
import csv
import json
import os
import time
from typing import Optional
from typing import Tuple

import httpx
from dotenv import load_dotenv

load_dotenv()


class FuelStopPreprocessor:
    NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"
    OUTPUT_FILE = "fuel_stops_processed.json"
    PROGRESS_FILE = "preprocessing_progress.json"

    def __init__(self):
        self.client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": "FuelOptimizer/1.0 (optimal-routing-preprocessing)"},
        )
        self.processed_count = 0
        self.failed_count = 0
        self.total_count = 0
        self.start_index = 0

    def load_progress(self):
        if os.path.exists(self.PROGRESS_FILE):
            with open(self.PROGRESS_FILE, "r") as f:
                progress = json.load(f)
                self.start_index = progress.get("last_processed_index", 0)
                print(f"Resuming from index {self.start_index}")

    def save_progress(self, current_index: int):
        progress = {
            "last_processed_index": current_index,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "timestamp": time.time(),
        }
        with open(self.PROGRESS_FILE, "w") as f:
            json.dump(progress, f)

    def geocode_address(self, address: str) -> Optional[Tuple[float, float]]:
        url = f"{self.NOMINATIM_BASE_URL}/search"
        params = {"q": address, "format": "json", "limit": 1, "countrycodes": "us"}

        response = self.client.get(url, params=params)
        response.raise_for_status()

        data = response.json()
        if not data:
            return None

        time.sleep(1)
        return (float(data[0]["lat"]), float(data[0]["lon"]))

    def process_all_fuel_stops(self, csv_file: str):
        fuel_stops = []

        if os.path.exists(self.OUTPUT_FILE) and self.start_index > 0:
            with open(self.OUTPUT_FILE, "r") as f:
                fuel_stops = json.load(f)
                print(f"Loaded {len(fuel_stops)} existing processed fuel stops")

        with open(csv_file, "r", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            all_rows = list(reader)
            self.total_count = len(all_rows)

            print(
                f"Processing {self.total_count} fuel stops starting from index {self.start_index}"
            )

            for i, row in enumerate(all_rows):
                if i < self.start_index:
                    continue

                print(
                    f"Processing {i + 1}/{self.total_count}: {row['Truckstop Name']} in {row['City']}, {row['State']}"
                )

                simple_address = f"{row['City'].strip()}, {row['State'].strip()}, USA"
                coordinates = self.geocode_address(simple_address)

                if coordinates:
                    fuel_stop = {
                        "truckstop_id": row["OPIS Truckstop ID"],
                        "name": row["Truckstop Name"],
                        "address": row["Address"],
                        "city": row["City"].strip(),
                        "state": row["State"].strip(),
                        "latitude": coordinates[0],
                        "longitude": coordinates[1],
                        "price_per_gallon": float(row["Retail Price"]),
                    }
                    fuel_stops.append(fuel_stop)
                    self.processed_count += 1
                else:
                    print(f"  Failed to geocode: {simple_address}")
                    self.failed_count += 1

                if (i + 1) % 50 == 0:
                    with open(self.OUTPUT_FILE, "w") as f:
                        json.dump(fuel_stops, f, indent=2)
                    self.save_progress(i + 1)
                    print(
                        f"  Saved progress: {self.processed_count} processed, {self.failed_count} failed"
                    )

        with open(self.OUTPUT_FILE, "w") as f:
            json.dump(fuel_stops, f, indent=2)

        print("\nPreprocessing complete!")
        print(f"Successfully processed: {self.processed_count}")
        print(f"Failed to geocode: {self.failed_count}")
        print(f"Output saved to: {self.OUTPUT_FILE}")

        if os.path.exists(self.PROGRESS_FILE):
            os.remove(self.PROGRESS_FILE)


def main():
    processor = FuelStopPreprocessor()
    processor.load_progress()
    processor.process_all_fuel_stops("fuel-prices-for-be-assessment.csv")


if __name__ == "__main__":
    main()
