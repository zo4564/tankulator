import requests
from bs4 import BeautifulSoup
import re
import time
import os
import django

# Konfiguracja Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tankulator.settings')
django.setup()
from core.models import FishSpecies

def get_numbers(text):
    """Wyciąga liczby z tekstu, np. '18 - 27°C' -> [18.0, 27.0]"""
    return [float(s) for s in re.findall(r"(\d+[\.,]?\d*)", text.replace(',', '.'))]

def extract_latin_name(soup):
    """Wyciąga nazwę łacińską z sekcji Podsumowanie"""
    try:
        summary_items = soup.find_all('li')
        for item in summary_items:
            text = item.get_text()
            if 'Nazwa ryby akwariowej:' in text:
                val_tag = item.find('b')
                if val_tag:
                    return val_tag.get_text().strip()
    except:
        pass
    return ""

def extract_hardness_from_summary(soup):
    """Wyciąga twardość bezpośrednio z sekcji 'Podsumowanie'"""
    try:
        summary_items = soup.find_all('li')
        for item in summary_items:
            text = item.get_text().lower()
            if 'twardość:' in text:
                val_tag = item.find('b')
                if val_tag:
                    numbers = get_numbers(val_tag.get_text())
                    if len(numbers) >= 2:
                        return numbers[0], numbers[1]
                    elif len(numbers) == 1:
                        return 0.0, numbers[0]
    except:
        pass
    return 5.0, 15.0

def get_all_fish_links(base_url, headers):
    """Przeczesuje spis alfabetyczny i zbiera linki do wszystkich ryb"""
    print(f"--- Zbieram linki ze spisu alfabetycznego ---")
    all_species_links = set()
    
    try:
        response = requests.get(base_url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Znajdź linki do wszystkich liter (A, B, C...)
        letter_nav = soup.find('div', class_='spis-a-z-navigation')
        if not letter_nav:
            print("BŁĄD: Nie znaleziono nawigacji alfabetycznej!")
            return []
            
        letter_links = [a['href'] for a in letter_nav.find_all('a', href=True)]
        
        # 2. Wejdź na każdą literę i wyciągnij linki do ryb
        for l_link in letter_links:
            print(f"Pobieram ryby na literę: {l_link.split('=')[-1]}")
            lr = requests.get(l_link, headers=headers, timeout=10)
            ls = BeautifulSoup(lr.content, 'html.parser')
            
            # Linki do ryb są wewnątrz <ul> z klasą 'spis-a-z'
            fish_list = ls.find('ul', class_='spis-a-z')
            if fish_list:
                for a in fish_list.find_all('a', href=True):
                    all_species_links.add(a['href'])
            time.sleep(0.3) # Delikatny delay przy zbieraniu linków
            
    except Exception as e:
        print(f"Błąd podczas zbierania linków: {e}")
        
    return list(all_species_links)

def scrape():
    # Zmieniamy URL startowy na spis alfabetyczny
    base_url = "https://rybyakwariowe.eu/spis-alfabetyczny/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    links = get_all_fish_links(base_url, headers)
    print(f"--- ZNALAZŁEM ŁĄCZNIE {len(links)} GATUNKÓW DO POBRANIA ---")

    for link in links:
        if not link.startswith('http'):
            link = "https://rybyakwariowe.eu" + link
        
        try:
            time.sleep(0.6)
            r = requests.get(link, headers=headers, timeout=10)
            r = requests.get(link, headers=headers, timeout=10)
            s = BeautifulSoup(r.content, 'html.parser')

            article_tag = s.find('article')
            if not article_tag: continue
            
            name = s.find('h1').get_text().strip()
            latin_name = extract_latin_name(s)
            h_min, h_max = extract_hardness_from_summary(s)
            
            entry_content = s.find('section', class_='entry-content')
            full_description = entry_content.get_text().lower() if entry_content else ""
            
            size_tag = s.find('li', class_='desc-fish__ico--size')
            biotope_tag = s.find('li', class_='desc-fish__ico--biotop')
            temp_tag = s.find('li', class_='desc-fish__ico--temp')
            ph_tag = s.find('li', class_='desc-fish__ico--ph')
            vol_tag = s.find('li', class_='desc-fish__ico--aquarium')

            if not all([temp_tag, ph_tag, vol_tag]): 
                print(f"⚠ Brak danych technicznych dla {name}, pomijam.")
                continue
            
            adult_size = max(get_numbers(size_tag.get_text())) if size_tag else 5.0
            origin_region = biotope_tag.get_text().replace('Biotop:', '').strip() if biotope_tag else "Inne"
            temps, phs, vols = get_numbers(temp_tag.get_text()), get_numbers(ph_tag.get_text()), get_numbers(vol_tag.get_text())

            # WYKRYWANIE ŁAWICOWOŚCI
            schooling_keywords = ['dla grupy', 'dla stada', 'ławica', 'ławicę', 'ławicy', 'ławicowa', 'stado', 'stadna', 'grupie', 'stadne', 'kilka sztuk', 'w grupach']
            is_schooling = any(word in full_description for word in schooling_keywords)

            full_text = (name + " " + full_description).lower()
            
            # WYKRYWANIE AGRESJI 
            # Słowniki wag dla agresji
            weights_3 = ['agresywny', 'agresywna', 'atakuje', 'bardzo agresywna', 'agresja']
            weights_2 = ['terytorialna', 'terytorialny', 'terytorialny', 'rewir', 'broni', 'hierarchia', 'hierarchię']
            weights_1 = ['łagodna', 'towarzyska', 'spokojna', 'towarzyskiego', 'pokojowa', 'pokojowy', 'łagodny', 'spokojny']

            # Liczenie punktów
            score_3 = sum(full_text.count(word) for word in weights_3) * 3  # Waga x3
            score_2 = sum(full_text.count(word) for word in weights_2) * 2  # Waga x2
            score_1 = sum(full_text.count(word) for word in weights_1) * 1  # Waga x1

            # Agresja - decyzja na podstawie najwyższego wyniku
            max_score = max(score_3, score_2, score_1)
            
            if max_score == 0:
                aggression = 1 
            elif max_score == score_3:
                aggression = 3
            elif max_score == score_2:
                aggression = 2
            else:
                aggression = 1

            # WYKRYWANIE STREFY (Zone)
            # Definicja wag dla stref
            weights_top = ['powierzchni', 'górna', 'górnej', 'tafla', 'pod powierzchnią', 'tafli']
            weights_mid = ['środkowa', 'środkowych', 'środkowej', 'toń', 'toni', 'wolna przestrzeń', 'wolnej przestrzeni']
            weights_btm = ['przy dnie', 'denna', 'dolnej', 'przekopuje', 'kopie']

            # Liczenie punktów dla stref
            score_top = sum(full_text.count(word) for word in weights_top)
            score_mid = sum(full_text.count(word) for word in weights_mid)
            score_btm = sum(full_text.count(word) for word in weights_btm)

            # Specjalne bonusy dla konkretnych grup (Heurystyka)
            if any(w in name.lower() for w in ['kirysek', 'zbrojnik', 'piskorek', 'bocja']):
                score_btm += 10  
            
            if any(w in name.lower() for w in ['pstrążeń', 'szczupieńczyk']):
                score_top += 10  

            if any(w in name.lower() for w in ['razbora', 'ławicowa']):
                score_mid += 10  

            # Wybór strefy na podstawie najwyższego wyniku
            max_zone_score = max(score_top, score_mid, score_btm)
            
            if max_zone_score == 0:
                zone = "MID"  # Domyślnie środek, jeśli tekst jest zbyt ubogi
            elif max_zone_score == score_top:
                zone = "TOP"
            elif max_zone_score == score_btm:
                zone = "BTM"
            else:
                zone = "MID"

            # Zapis do bazy
            fish_data = {
                'latin_name': latin_name,
                'temp_min': temps[0] if temps else 22,
                'temp_max': temps[1] if len(temps) > 1 else 26,
                'ph_min': phs[0] if phs else 6.5,
                'ph_max': phs[1] if len(phs) > 1 else 7.5,
                'hardness_min': h_min,
                'hardness_max': h_max,
                'min_tank_volume': vols[0] if vols else 60,
                'bioload_index': round(adult_size / 10.0, 2),
                'is_schooling': is_schooling,
                'adult_size': adult_size,
                'origin_region': origin_region,
                'aggression_level': aggression,
                'zone': zone
            }

            obj, created = FishSpecies.objects.update_or_create(
                name=name,
                defaults=fish_data
            )

            # print wszystkich danych
            status = "NOWY" if created else "ZAKTUALIZOWANO"
            print(f"\n{'='*50}")
            print(f"[{status}] {name}")
            print(f"{'-'*50}")
            print(f"  Nazwa łacińska: {fish_data['latin_name']}")
            print(f"  Pochodzenie:     {fish_data['origin_region']}")
            print(f"  Temperatura:    {fish_data['temp_min']} - {fish_data['temp_max']} °C")
            print(f"  pH:             {fish_data['ph_min']} - {fish_data['ph_max']}")
            print(f"  Twardość (dH):  {fish_data['hardness_min']} - {fish_data['hardness_max']}")
            print(f"  Min. litraż:    {fish_data['min_tank_volume']} L")
            print(f"  Rozmiar ryby:   {fish_data['adult_size']} cm")
            print(f"  Strefa:         {fish_data['zone']}")
            print(f"  Agresja (1-3):  {fish_data['aggression_level']}")
            print(f"  Stadna:         {'Tak' if fish_data['is_schooling'] else 'Nie'}")
            print(f"{'='*50}")

        except Exception as e:
            print(f"✘ Błąd przy {link}: {e}")

if __name__ == "__main__":
    scrape()