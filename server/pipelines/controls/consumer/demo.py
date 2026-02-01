"""Demo script for ControlsConsumer module.

This script demonstrates the consumer functionality with graph traversal
and temporal queries.

Usage:
    python -m server.pipelines.consumer.demo
"""

import asyncio
from datetime import datetime

from server.pipelines.controls.consumer import ControlsConsumer
from server.logging_config import get_logger


logger = get_logger(name=__name__)


async def demo():
    """Demonstrate consumer functionality with graph traversal."""
    print("=" * 70)
    print("CONSUMER DEMO - With Graph Traversal")
    print("=" * 70)

    async with ControlsConsumer() as consumer:
        # Get table counts
        print("\n" + "-" * 70)
        print("1. TABLE COUNTS (including graph edges)")
        print("-" * 70)
        counts = await consumer.get_table_counts()
        for table, count in counts.items():
            print(f"  {table}: {count}")

        if counts.get("src_controls_main", 0) == 0:
            print("\n  WARNING: No data in database. Run ingest module first.")
            return

        # Get current snapshot
        print("\n" + "-" * 70)
        print("2. CURRENT SNAPSHOT (with lookups)")
        print("-" * 70)
        snapshot = await consumer.get_current_snapshot(include_lookups=True)
        print(f"  Snapshot summary: {snapshot.summary()}")

        if not snapshot.controls_main:
            print("\n  WARNING: No controls in database.")
            return

        sample_control_id = snapshot.controls_main[0].get('control_id')
        print(f"\n  Sample control_id: {sample_control_id}")

        # Get control with relationships via graph traversal
        print("\n" + "-" * 70)
        print("3. GET CONTROL WITH RELATIONSHIPS (Graph Traversal)")
        print("-" * 70)
        full_record = await consumer.get_control_with_relationships(sample_control_id)
        print(f"  Control ID: {full_record.control_id}")
        print(f"  Relationship summary: {full_record.summary()}")
        if full_record.risk_themes:
            print(f"  Sample risk theme: {full_record.risk_themes[0]}")
        if full_record.functions:
            print(f"  Sample function: {full_record.functions[0]}")

        # Get controls by risk theme (reverse graph traversal)
        print("\n" + "-" * 70)
        print("4. GET CONTROLS BY RISK THEME (Reverse Graph Traversal)")
        print("-" * 70)
        if snapshot.risk_themes:
            sample_risk_theme_id = snapshot.risk_themes[0].get('risk_theme_id')
            print(f"  Looking for controls with risk theme: {sample_risk_theme_id}")
            controls = await consumer.get_controls_by_risk_theme(sample_risk_theme_id)
            print(f"  Found {len(controls)} controls")
            if controls:
                print(f"  Sample control_ids: {[c.get('control_id') for c in controls[:3]]}")
        else:
            print("  No risk themes in database")

        # Get control graph (with edge metadata)
        print("\n" + "-" * 70)
        print("5. GET CONTROL GRAPH (with edge metadata)")
        print("-" * 70)
        graph = await consumer.get_control_graph(sample_control_id)
        print(f"  Control ID: {graph.get('control_id')}")
        print(f"  Risk theme edges: {len(graph.get('risk_theme_edges', []))}")
        print(f"  Related function edges: {len(graph.get('related_function_edges', []))}")
        print(f"  Related location edges: {len(graph.get('related_location_edges', []))}")
        print(f"  SOX edges: {len(graph.get('sox_edges', []))}")
        print(f"  Category flag edges: {len(graph.get('category_flag_edges', []))}")
        print(f"  Taxonomy edges: {len(graph.get('taxonomy_edges', []))}")
        print(f"  Enrichment edges: {len(graph.get('enrichment_edges', []))}")
        print(f"  Cleaned text edges: {len(graph.get('cleaned_text_edges', []))}")
        print(f"  Embeddings edges: {len(graph.get('embeddings_edges', []))}")

        # Get complete control record (assembled from all tables + relationships)
        print("\n" + "-" * 70)
        print("6. GET COMPLETE CONTROL RECORD (Assembled Dict)")
        print("-" * 70)
        import json
        complete_record = await consumer.get_complete_control_record(sample_control_id)
        print(f"  Control ID: {complete_record['control_id']}")
        print(f"\n  Structure:")
        if complete_record['controls_main']:
            keys = list(complete_record['controls_main'].keys())
            print(f"    - controls_main: {keys[:5]}..." if len(keys) > 5 else f"    - controls_main: {keys}")
        else:
            print("    - controls_main: None")
        print(f"    - relationships.risk_themes: {len(complete_record['relationships']['risk_themes'])} items")
        print(f"    - relationships.functions: {len(complete_record['relationships']['functions'])} items")
        print(f"    - relationships.locations: {len(complete_record['relationships']['locations'])} items")
        print(f"    - relationships.sox_assertions: {len(complete_record['relationships']['sox_assertions'])} items")
        print(f"    - relationships.category_flags: {len(complete_record['relationships']['category_flags'])} items")
        print(f"    - model_outputs.taxonomy: {'present' if complete_record['model_outputs']['taxonomy'] else 'None'}")
        print(f"    - model_outputs.enrichment: {'present' if complete_record['model_outputs']['enrichment'] else 'None'}")
        print(f"    - model_outputs.clean_text: {'present' if complete_record['model_outputs']['clean_text'] else 'None'}")
        print(f"    - model_outputs.embeddings: {'present' if complete_record['model_outputs']['embeddings'] else 'None'}")

        if complete_record['relationships']['risk_themes']:
            print(f"\n  Sample risk_theme:")
            print(f"    {json.dumps(complete_record['relationships']['risk_themes'][0], indent=6, default=str)}")

        if complete_record['model_outputs']['taxonomy']:
            print(f"\n  Sample taxonomy output:")
            tax = complete_record['model_outputs']['taxonomy']
            print(f"    primary_nfr_risk_theme: {tax.get('primary_nfr_risk_theme')}")
            print(f"    primary_risk_theme_id: {tax.get('primary_risk_theme_id')}")

        # Get record as of date (temporal)
        print("\n" + "-" * 70)
        print("7. GET RECORD AS OF DATE (Temporal Query)")
        print("-" * 70)
        today = datetime.now().isoformat()
        record = await consumer.get_record_as_of_date(sample_control_id, today)
        print(f"  Control ID: {record.control_id}")
        print(f"  As of date: {record.as_of_date}")
        print(f"  Actual date: {record.actual_date}")
        print(f"  Fallback used: {record.fallback_used}")

        # Get record history
        print("\n" + "-" * 70)
        print("8. GET RECORD HISTORY")
        print("-" * 70)
        history = await consumer.get_record_history(sample_control_id)
        print(f"  Control ID: {history.control_id}")
        print(f"  Version counts: {history.version_counts()}")

        print("\n" + "=" * 70)
        print("DEMO COMPLETE")
        print("=" * 70)


async def main():
    """Run the consumer demo."""
    try:
        await demo()
    except Exception as e:
        logger.error(f"Demo failed: {str(e)}", exc_info=True)
        print(f"\nERROR: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
