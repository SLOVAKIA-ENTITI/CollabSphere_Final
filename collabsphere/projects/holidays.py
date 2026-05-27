from datetime import date, timedelta

def get_easter_sunday(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def get_slovak_holidays(year):
    holidays = {
        date(year, 1, 1): "Deň vzniku SR",
        date(year, 1, 6): "Traja králi",
        date(year, 5, 1): "Sviatok práce",
        date(year, 5, 8): "Deň víťazstva nad fašizmom",
        date(year, 7, 5): "Sviatok sv. Cyrila a Metoda",
        date(year, 8, 29): "Výročie SNP",
        date(year, 9, 1): "Deň Ústavy SR",
        date(year, 9, 15): "Sedembolestná Panna Mária",
        date(year, 11, 1): "Sviatok všetkých svätých",
        date(year, 11, 17): "Deň boja za slobodu a demokraciu",
        date(year, 12, 24): "Štedrý deň",
        date(year, 12, 25): "1. sviatok vianočný",
        date(year, 12, 26): "2. sviatok vianočný",
    }
    
    easter_sunday = get_easter_sunday(year)
    holidays[easter_sunday - timedelta(days=2)] = "Veľký piatok"
    holidays[easter_sunday + timedelta(days=1)] = "Veľkonočný pondelok"
    
    return holidays
