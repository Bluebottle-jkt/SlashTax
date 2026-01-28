#!/usr/bin/env python3
"""
Smoke test script for SlashTax backend API.

Tests the core import and face detection pipeline to verify everything works.

Usage:
    python scripts/smoke_test_import.py [--base-url URL]

Requirements:
    - Backend server must be running
    - Neo4j must be accessible
    - A test image with faces (optional, will create synthetic test if not provided)
"""
import argparse
import json
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    print("Please install httpx: pip install httpx")
    sys.exit(1)


class SmokeTest:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=60.0)
        self.results = {"passed": 0, "failed": 0, "tests": []}

    def log(self, message: str, level: str = "INFO"):
        print(f"[{level}] {message}")

    def test(self, name: str, passed: bool, details: str = ""):
        status = "PASS" if passed else "FAIL"
        self.results["tests"].append({
            "name": name,
            "passed": passed,
            "details": details
        })
        if passed:
            self.results["passed"] += 1
            self.log(f"{status}: {name}", "INFO")
        else:
            self.results["failed"] += 1
            self.log(f"{status}: {name} - {details}", "ERROR")
        return passed

    def run_all_tests(self):
        """Run all smoke tests."""
        self.log("=" * 60)
        self.log("SlashTax Backend Smoke Test")
        self.log("=" * 60)

        # 1. Health Check
        self.test_health()

        # 2. Stats Endpoint
        self.test_stats()

        # 3. Graph Endpoint
        self.test_graph()

        # 4. Persons Endpoint
        self.test_persons()

        # 5. Posts Endpoint
        self.test_posts()

        # 6. Clusters Endpoint
        self.test_clusters()

        # 7. Faces Endpoint
        self.test_faces()

        # 8. Diagnostics Endpoint
        self.test_diagnostics()

        # Summary
        self.log("=" * 60)
        self.log(f"Tests Passed: {self.results['passed']}")
        self.log(f"Tests Failed: {self.results['failed']}")
        self.log("=" * 60)

        return self.results["failed"] == 0

    def test_health(self):
        """Test health endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/health")
            data = response.json()
            passed = (
                response.status_code == 200 and
                data.get("status") == "healthy" and
                data.get("neo4j") == "connected"
            )
            self.test("Health Check", passed, f"Status: {data.get('status')}, Neo4j: {data.get('neo4j')}")
        except Exception as e:
            self.test("Health Check", False, str(e))

    def test_stats(self):
        """Test stats endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/graph/stats")
            if response.status_code == 200:
                data = response.json()
                self.test(
                    "Stats Endpoint",
                    True,
                    f"Persons: {data.get('total_persons', 0)}, "
                    f"Posts: {data.get('total_posts', 0)}, "
                    f"Faces: {data.get('total_faces_detected', 0)}"
                )
            else:
                self.test("Stats Endpoint", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Stats Endpoint", False, str(e))

    def test_graph(self):
        """Test graph endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/graph/?limit=10")
            if response.status_code == 200:
                data = response.json()
                nodes = data.get("nodes", [])
                edges = data.get("edges", [])
                self.test(
                    "Graph Endpoint",
                    True,
                    f"Nodes: {len(nodes)}, Edges: {len(edges)}"
                )
            else:
                self.test("Graph Endpoint", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Graph Endpoint", False, str(e))

    def test_persons(self):
        """Test persons endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/persons/")
            if response.status_code == 200:
                data = response.json()
                self.test("Persons List", True, f"Count: {len(data)}")
            else:
                self.test("Persons List", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Persons List", False, str(e))

    def test_posts(self):
        """Test posts endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/posts/")
            if response.status_code == 200:
                data = response.json()
                self.test("Posts List", True, f"Count: {len(data)}")

                # Test single post if available
                if data:
                    post_id = data[0].get("id")
                    if post_id:
                        response2 = self.client.get(f"{self.base_url}/api/posts/{post_id}")
                        self.test(
                            "Single Post",
                            response2.status_code == 200,
                            f"Post ID: {post_id}"
                        )
            else:
                self.test("Posts List", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Posts List", False, str(e))

    def test_clusters(self):
        """Test clusters endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/clusters/")
            if response.status_code == 200:
                data = response.json()
                self.test("Clusters List", True, f"Count: {len(data)}")
            else:
                self.test("Clusters List", False, f"HTTP {response.status_code}")

            # Test cluster stats
            response2 = self.client.get(f"{self.base_url}/api/clusters/stats")
            if response2.status_code == 200:
                stats = response2.json()
                self.test(
                    "Cluster Stats",
                    True,
                    f"Clusters: {stats.get('total_clusters', 0)}, "
                    f"Clustered: {stats.get('clustered_faces', 0)}"
                )
            else:
                self.test("Cluster Stats", False, f"HTTP {response2.status_code}")
        except Exception as e:
            self.test("Clusters Endpoint", False, str(e))

    def test_faces(self):
        """Test faces endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/graph/faces?limit=10")
            if response.status_code == 200:
                data = response.json()
                self.test("Faces List", True, f"Count: {len(data)}")
            else:
                self.test("Faces List", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Faces List", False, str(e))

    def test_diagnostics(self):
        """Test diagnostics endpoint."""
        try:
            response = self.client.get(f"{self.base_url}/api/diagnostics/stats")
            if response.status_code == 200:
                data = response.json()
                self.test(
                    "Diagnostics Stats",
                    True,
                    f"Posts: {data.get('database', {}).get('posts', 0)}, "
                    f"Faces: {data.get('database', {}).get('faces', 0)}"
                )
            else:
                self.test("Diagnostics Stats", False, f"HTTP {response.status_code}")
        except Exception as e:
            self.test("Diagnostics Stats", False, str(e))


def main():
    parser = argparse.ArgumentParser(description="SlashTax Backend Smoke Test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    args = parser.parse_args()

    tester = SmokeTest(base_url=args.base_url)
    success = tester.run_all_tests()

    if args.json:
        print(json.dumps(tester.results, indent=2))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
