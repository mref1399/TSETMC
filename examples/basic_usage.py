#!/usr/bin/env python3
"""
Basic usage example for Iran Stock Analyzer
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.data_manager import DataManager
from rich.console import Console
from rich.table import Table
import json

def main():
    console = Console()
    
    # Initialize data manager
    # Make sure to set BRS_API_KEY environment variable
    try:
        data_manager = DataManager()
        console.print("[green]Data manager initialized successfully[/green]")
    except Exception as e:
        console.print(f"[red]Error initializing data manager: {e}[/red]")
        return
    
    # Health check
    console.print("\n[bold]Health Check[/bold]")
    health = data_manager.health_check()
    console.print(json.dumps(health, indent=2, ensure_ascii=False))
    
    # Get all symbols
    console.print("\n[bold]Fetching all symbols...[/bold]")
    symbols = data_manager.get_all_symbols()
    
    if symbols:
        console.print(f"[green]Found {len(symbols)} symbols[/green]")
        
        # Show first 10 symbols in a table
        table = Table(title="First 10 Symbols")
        table.add_column("Symbol", style="cyan")
        table.add_column("Name", style="magenta")
        
        for symbol in symbols[:10]:
            if isinstance(symbol, dict):
                symbol_name = symbol.get('symbol', 'N/A')
                company_name = symbol.get('name', 'N/A')
                table.add_row(str(symbol_name), str(company_name))
        
        console.print(table)
    else:
        console.print("[red]No symbols found[/red]")
    
    # Cache statistics
    console.print("\n[bold]Cache Statistics[/bold]")
    cache_stats = data_manager.get_cache_stats()
    console.print(json.dumps(cache_stats, indent=2))

if __name__ == "__main__":
    main()
