import json
from urllib.parse import urldefrag

def main():
    try:
        with open('dataset_dump.json', 'r') as f:
            dataset = json.load(f)
    except Exception as e:
        print(f"Error loading dataset: {e}")
        return

    pages = dataset.get('pages', [])
    crawl_stats = dataset.get('crawl_stats', {})
    
    print("--- CRAWL STATS ---")
    for k, v in crawl_stats.items():
        print(f"{k}: {v}")
    
    total_pages = len(pages)
    article_pages = 0
    product_pages = 0
    eligible_zero_links = 0
    
    pages_with_images = 0
    total_images_observed = 0
    total_images_with_alt = 0
    total_images_missing_alt = 0
    
    for page in pages:
        status = page.get('status_code', 0)
        extracted = page.get('extracted', {})
        page_type = extracted.get('page_type', 'unknown')
        
        # URL
        url = page.get('url', '')
        final_url = page.get('final_url') or url
        page_base_url, _ = urldefrag(final_url)
        
        # Navigation metrics
        if status == 200:
            if page_type == 'article':
                article_pages += 1
            elif page_type == 'product':
                product_pages += 1
                
            if page_type in ['article', 'product']:
                internal_links = extracted.get('internal_links', [])
                valid_outbound_links = set()
                for link in internal_links:
                    clean_link, _ = urldefrag(link)
                    if clean_link != page_base_url:
                        valid_outbound_links.add(clean_link)
                if len(valid_outbound_links) == 0:
                    eligible_zero_links += 1
                    
        # Media metrics
        if status == 200:
            image_urls = extracted.get('image_urls', [])
            image_alts = extracted.get('image_alts', [])
            
            t_imgs = len(image_urls)
            if t_imgs > 0:
                pages_with_images += 1
                total_images_observed += t_imgs
                
                valid_alts = [alt for alt in image_alts if alt.strip()]
                t_valid = len(valid_alts)
                t_missing = t_imgs - t_valid
                
                total_images_with_alt += t_valid
                total_images_missing_alt += t_missing

    print("\n--- PHASE 7 EVALUATION EVIDENCE ---")
    print(f"total_pages_evaluated: {total_pages}")
    print(f"article_pages: {article_pages}")
    print(f"product_pages: {product_pages}")
    print(f"eligible_zero_links: {eligible_zero_links}")
    print(f"pages_with_images: {pages_with_images}")
    print(f"total_images_observed: {total_images_observed}")
    print(f"total_images_with_alt: {total_images_with_alt}")
    print(f"total_images_missing_alt: {total_images_missing_alt}")

if __name__ == '__main__':
    main()
