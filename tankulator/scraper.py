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

def scrape():
    # URL listy najpopularniejszych ryb
    list_url = "https://rybyakwariowe.eu/gatunki-ryb-akwariowych/najpopularniejsze-ryby-akwariowe/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print(f"--- START: Pobieram stronę listy: {list_url} ---")
    try:
        response = requests.get(list_url, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"BŁĄD POŁĄCZENIA: {e}")
        return

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # SZUKANIE LINKÓW: Szukamy wszystkich linków, które w adresie mają '/ryba-akwariowa/'
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if "/ryba-akwariowa/" in href:
            links.append(href)
    
    # Usuwamy duplikaty
    links = list(set(links))
    print(f"--- ZNALAZŁEM {len(links)} LINKÓW DO RYB ---")

    if not links:
        print("UWAGA: Nie znaleziono linków. Strona mogła zmienić strukturę.")
        return

    for link in links:
        if not link.startswith('http'):
            link = "https://rybyakwariowe.eu" + link
        if "#" in link: continue

        try:
            time.sleep(0.5)
            r = requests.get(link, headers=headers, timeout=10)
            s = BeautifulSoup(r.content, 'html.parser')

            name = s.find('h1').get_text().strip()
            
            # Pobieramy cały tekst opisu, żeby w nim szukać słów kluczowych
            full_description = s.find('section', class_='entry-content').get_text().lower()
            
            size_tag = s.find('li', class_='desc-fish__ico--size')
            biotope_tag = s.find('li', class_='desc-fish__ico--biotop')
            
            # Pobieranie rozmiaru (szukamy max rozmiaru z zakresu)
            adult_size = 5.0 # domyślnie
            if size_tag:
                sizes = get_numbers(size_tag.get_text())
                adult_size = max(sizes) if sizes else 5.0

            # Pobieranie biotopu (regionu)
            origin_region = "Inne"
            if biotope_tag:
                origin_region = biotope_tag.get_text().replace('Biotop:', '').strip()

            # 1. WYKRYWANIE ŁAWICOWOŚCI
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

            # 3. WYKRYWANIE STREFY (Zone)
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

            # Reszta parametrów (Temp, pH, Vol) - tak jak wcześniej
            temp_tag = s.find('li', class_='desc-fish__ico--temp')
            ph_tag = s.find('li', class_='desc-fish__ico--ph')
            vol_tag = s.find('li', class_='desc-fish__ico--aquarium')
            
            if not all([temp_tag, ph_tag, vol_tag]): continue
            
            temps = get_numbers(temp_tag.get_text())
            phs = get_numbers(ph_tag.get_text())
            vols = get_numbers(vol_tag.get_text())

            # Zapis/Aktualizacja w bazie
            FishSpecies.objects.update_or_create(
                name=name,
                defaults={
                    'temp_min': temps[0] if temps else 22,
                    'temp_max': temps[1] if len(temps) > 1 else 26,
                    'ph_min': phs[0] if phs else 6.5,
                    'ph_max': phs[1] if len(phs) > 1 else 7.5,
                    'min_tank_volume': vols[0] if vols else 60,
                    'is_schooling': is_schooling,
                    'aggression_level': aggression,
                    'zone': zone
                }
            )
            
            traits = f"{'ŁAWICOWA' if is_schooling else 'SOLO'} | AGRESJA:{aggression} | STREFA:{zone}"
            print(f"✔ {name} -> {traits}")

        except Exception as e:
            print(f"✘ Błąd przy {link}: {e}")

if __name__ == "__main__":
    scrape() 