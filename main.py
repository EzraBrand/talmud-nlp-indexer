"""
Main script for running the Talmud NLP Indexer.
"""
import json
import os
from talmud_indexer import TalmudProcessor


def main():
    """Run the Talmud NLP Indexer."""
    # Initialize processor
    processor = TalmudProcessor()
    
    # Define the target pages (first 10 pages of Berakhot)
    tractate = "Berakhot"
    start_daf = "2a"  # Talmud usually starts at page 2
    end_daf = "7a"    # This covers 10 pages (2a, 2b, 3a, 3b, ..., 7a)
    
    # Create directory for output
    os.makedirs("data", exist_ok=True)
    
    # Process each page
    for num in range(2, 8):  # Pages 2-7
        for side in ['a', 'b']:
            # Skip 7b as it's the 11th page
            if num == 7 and side == 'b':
                continue
                
            daf = f"{num}{side}"
            print(f"Processing {tractate}.{daf}...")
            
            try:
                # Process the page
                result = processor.process_daf(tractate, daf)
                
                # Save results
                output_file = f"data/{tractate}_{daf}.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    # Convert complex objects to strings for JSON serialization
                    serializable_result = result.copy()
                    serializable_result['en_processed'] = {
                        k: v for k, v in result['en_processed'].items() 
                        if k in ['entities', 'noun_phrases', 'sentences']
                    }
                    serializable_result['he_processed'] = {
                        'embedding_shape': result['he_processed']['embeddings'].shape,
                    }
                    
                    json.dump(serializable_result, f, ensure_ascii=False, indent=2)
                
                print(f"Saved results to {output_file}")
                
                # Print tags
                print(f"Tags: {', '.join(result['tags'])}")
                print("-" * 50)
                
            except Exception as e:
                print(f"Error processing {tractate}.{daf}: {e}")
    
    print("Processing complete!")


if __name__ == "__main__":
    main()