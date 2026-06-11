import pygame
import random
import requests  # API uchun kutubxona

# Telegram sozlamalari
BOT_TOKEN = "8882891997:AAF60kIoiDTlxb0XNNPUIZMCd8lL7BtksI0"
CHAT_ID = "7578712290"


def send_score_to_telegram(score):
    yulduzlar = score // 10
    message = f"🎮 O'yin yakunlandi!\nHisob: {score}\nQo'lga kiritilgan yulduzlar: {yulduzlar} ⭐"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage?chat_id={CHAT_ID}&text={message}"
    requests.get(url)


pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
font = pygame.font.SysFont("Arial", 28)

score = 0
circles = []


def add_circle():
    radius = random.randint(20, 50)
    x = random.randint(radius, WIDTH - radius)
    y = random.randint(radius, HEIGHT - radius)
    circles.append({'x': x, 'y': y, 'radius': radius, 'timer': 100})


running = True
while running:
    screen.fill((20, 20, 30))

    spawn_rate = max(10, 40 - (score // 5))
    if random.randint(0, spawn_rate) == 0:
        add_circle()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            # O'yin yopilganda natijani yuborish
            send_score_to_telegram(score)
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = pygame.mouse.get_pos()
            hit = False
            for c in circles[:]:
                if ((c['x'] - mx) ** 2 + (c['y'] - my) ** 2) ** 0.5 < c['radius']:
                    circles.remove(c)
                    score += 1
                    hit = True
            if not hit: score = max(0, score - 1)

    for c in circles[:]:
        c['timer'] -= (1 + (score // 10))
        if c['timer'] <= 0:
            circles.remove(c)
        else:
            pygame.draw.circle(screen, (255, 200, 0), (c['x'], c['y']), c['radius'], 2)

    screen.blit(font.render(f"Hisob: {score}", True, (255, 255, 255)), (20, 20))
    screen.blit(font.render(f"Yulduzlar: {score // 10}", True, (255, 215, 0)), (20, 50))

    pygame.display.flip()
    pygame.time.Clock().tick(60)

pygame.quit()