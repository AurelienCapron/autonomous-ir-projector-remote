import machine
import time
import utime

# ========================================================
# CONFIGURATION GÉNÉRALE
# ========================================================
ACTIVER_SON = True
ACTIVER_MOUVEMENT = True
ACTIVER_PRESENCE = True
DELAI_INACTIVITE_SEC = 5400  # 1h30 (Mettre à 10 pour les tests)

# ========================================================
# VALEURS PAR DÉFAUT (PROJECTEUR DE LA SALLE DES CONSEILS)
# ========================================================
NEC_B1 = 0x83
NEC_B2 = 0x55
NEC_B3 = 0x90
NEC_B4 = 0x6F

# ========================================================
# CONFIGURATION DES BROCHES
# ========================================================
# Entrées Numériques (Présence et État Projecteur)
capteur_son = machine.Pin(21, machine.Pin.IN, machine.Pin.PULL_DOWN)
mmwave_1 = machine.Pin(16, machine.Pin.IN, machine.Pin.PULL_DOWN)
mmwave_2 = machine.Pin(17, machine.Pin.IN, machine.Pin.PULL_DOWN)
pin_etat_projecteur = machine.Pin(2, machine.Pin.IN, machine.Pin.PULL_DOWN)

# Entrées Analogiques (ADC)
ldr_1 = machine.ADC(26)         # Photorésistance 1
ldr_2 = machine.ADC(27)         # Photorésistance 2
potentiometre = machine.ADC(28) # Potentiomètre de réglage du seuil

# Entrées/Sorties Infrarouge & Apprentissage
led_presence = machine.Pin(0, machine.Pin.OUT)
bouton_apprentissage = machine.Pin(19, machine.Pin.IN, machine.Pin.PULL_UP)
recepteur_ir = machine.Pin(18, machine.Pin.IN, machine.Pin.PULL_UP)

# Broche de sortie pour la LED témoin projecteur
led_projecteur = machine.Pin(1, machine.Pin.OUT)

# Configuration de la LED IR 1 (Émetteur 1 sur GPIO 7)
led_ir = machine.PWM(machine.Pin(7))
led_ir.freq(38000)
led_ir.duty_u16(0)

# Configuration de la LED IR 2 (Émetteur 2 sur GPIO 14)
led_ir_2 = machine.PWM(machine.Pin(14))
led_ir_2.freq(38000)
led_ir_2.duty_u16(0)

# ========================================================
# UTILITAIRES & FONCTION MAP
# ========================================================
def map_valeur(valeur, in_min, in_max, out_min, out_max):
    return int((valeur - in_min) * (out_max - out_min) / (in_max - in_min) + out_min)

# ========================================================
# FONCTIONS : ÉMISSION INFRAROUGE (NEC)
# ========================================================
def mark(duree_us):
    # On active le signal à 50% sur les DEUX leds en même temps
    led_ir.duty_u16(32768)
    led_ir_2.duty_u16(32768)
    utime.sleep_us(duree_us)
    # On coupe le signal sur les deux leds
    led_ir.duty_u16(0)
    led_ir_2.duty_u16(0)

def space(duree_us):
    led_ir.duty_u16(0)
    led_ir_2.duty_u16(0)
    utime.sleep_us(duree_us)

def zero(): mark(562); space(562)
def one(): mark(562); space(1675)

def envoyer_code_nec_universel():
    global NEC_B1, NEC_B2, NEC_B3, NEC_B4
    print(f"\n[IR] Envoi du code d'extinction -> [{hex(NEC_B1)}, {hex(NEC_B2)}, {hex(NEC_B3)}, {hex(NEC_B4)}]")
    
    # --- DÉBUT DU DEBUG BITS ---
    # On génère un aperçu de ce qui va être réellement envoyé dans les airs
    debug_str = ""
    for octet in [NEC_B1, NEC_B2, NEC_B3, NEC_B4]:
        for i in range(8):
            bit = (octet >> i) & 1
            debug_str += str(bit)
        debug_str += " " # Espace entre chaque octet pour la lisibilité
    
    # Affichage dans la console
    print(f"[BITS] Séquence générée : {debug_str}")
    
    # On boucle 3 fois pour forcer le projecteur à prendre la commande
    for envoi in range(3):
        # Petit log pour suivre les 3 tirs
        print(f"   -> Tir {envoi + 1}/3...") 
        
        mark(9000)
        space(4500)
        for octet in [NEC_B1, NEC_B2, NEC_B3, NEC_B4]:
            for i in range(8):
                if (octet >> i) & 1: 
                    one()
                else: 
                    zero()
        mark(562)
        
        # On coupe les LEDs
        led_ir.duty_u16(0)
        led_ir_2.duty_u16(0)
        
        # Pause obligatoire de 50ms entre deux envois NEC
        time.sleep(0.5)

# ========================================================
# FONCTION : APPRENTISSAGE INFRAROUGE (SNIFFER)
# ========================================================
def lancer_mode_apprentissage():
    global NEC_B1, NEC_B2, NEC_B3, NEC_B4
    for _ in range(3):
        led_presence.value(1); time.sleep(0.2)
        led_presence.value(0); time.sleep(0.2)
        
    print("\n[MODE APPRENTISSAGE ACTIF]")
    print("Pointez la télécommande vers le capteur et appuyez sur 'Power'...")
    
    debut_attente = time.ticks_ms()
    while recepteur_ir.value() == 1:
        if time.ticks_diff(time.ticks_ms(), debut_attente) > 10000:
            print("[TIMEOUT] Aucun signal reçu. Retour au mode normal.")
            return

    historique = []
    etat_actuel = 0
    debut_capture = time.ticks_us()
    
    while time.ticks_diff(time.ticks_us(), debut_capture) < 100000:
        nouvel_etat = recepteur_ir.value()
        if nouvel_etat != etat_actuel:
            historique.append(time.ticks_us())
            etat_actuel = nouvel_etat
            
    durees = [time.ticks_diff(historique[i], historique[i-1]) for i in range(1, len(historique))]
    
    if len(durees) >= 67 and durees[0] > 8000:
        bits = [1 if durees[i] > 1200 else 0 for i in range(3, 67, 2)]
        NEC_B1 = sum(bits[0+i] << i for i in range(8))
        NEC_B2 = sum(bits[8+i] << i for i in range(8))
        NEC_B3 = sum(bits[16+i] << i for i in range(8))
        NEC_B4 = sum(bits[24+i] << i for i in range(8))
        print(f"[SUCCÈS] Nouveau code enregistré : [{hex(NEC_B1)}, {hex(NEC_B2)}, {hex(NEC_B3)}, {hex(NEC_B4)}]\n")
        led_presence.value(1); time.sleep(2); led_presence.value(0)
    else:
        print("[ERREUR] Signal illisible ou non conforme au protocole NEC.\n")

# ========================================================
# BOUCLE PRINCIPALE
# ========================================================
print("--- Système de gestion complet démarré ---")

presence_globale = False
dernier_mouvement_temps = time.time()
ir_deja_envoye = False
temps_pression_bouton = 0
bouton_en_cours = False

try:
    while True:
        # 1. GESTION DU BOUTON (Appui long de 3 secondes)
        if bouton_apprentissage.value() == 0:  # Déclenchement à 0 suite au PULL_UP
            if not bouton_en_cours:
                temps_pression_bouton = time.ticks_ms()
                bouton_en_cours = True
            elif time.ticks_diff(time.ticks_ms(), temps_pression_bouton) > 3000:
                lancer_mode_apprentissage()
                bouton_en_cours = False 
                while bouton_apprentissage.value() == 0:
                    time.sleep(0.1)
                dernier_mouvement_temps = time.time() 
        else:
            bouton_en_cours = False

        # 2. LECTURE DE LA LUMINOSITÉ ET DU POTENTIOMÈTRE
        val_ldr1 = ldr_1.read_u16()
        val_ldr2 = ldr_2.read_u16()
        val_pot  = potentiometre.read_u16()
        
        # Ajustement de la plage du seuil (ici réglable de 30000 à 65535)
        seuil_dynamique = map_valeur(val_pot, 0, 65535, 30000, 50000)
        
        # Sécurité : trop de lumière si l'une des deux LDR passe sous le seuil
        trop_de_lumiere = (val_ldr1 > seuil_dynamique) or (val_ldr2 > seuil_dynamique)

        # 3. LECTURE DES CAPTEURS DE PRÉSENCE
        son_actif = (capteur_son.value() == 1) and ACTIVER_SON
        mouvement_1_actif = (mmwave_1.value() == 1) and ACTIVER_MOUVEMENT
        mouvement_2_actif = (mmwave_2.value() == 1) and ACTIVER_PRESENCE
        
        # 4. LOGIQUE DE PRÉSENCE
        if son_actif or mouvement_1_actif or mouvement_2_actif:
            dernier_mouvement_temps = time.time()
            ir_deja_envoye = False
            
            if not presence_globale:
                capteurs_actifs = []
                if son_actif: capteurs_actifs.append("Capteur Sonore")
                if mouvement_1_actif: capteurs_actifs.append("Capteur mouvement")
                if mouvement_2_actif: capteurs_actifs.append("Capteur présence")
                
                liste_capteurs = ", ".join(capteurs_actifs)
                print(f"[PRÉSENCE] -> Personne détectée par : {liste_capteurs} !")
                
            presence_globale = True
            led_presence.value(1)
        else:
            if presence_globale:
                print("[PRÉSENCE] -> Salle vide. Le chronomètre démarre.")
            presence_globale = False
            led_presence.value(0)

        # 5. GESTION DE L'EXTINCTION AUTOMATIQUE OU SÉCURITÉ LUMIÈRE
        projecteur_est_allume = (pin_etat_projecteur.value() == 1)

        if projecteur_est_allume and not ir_deja_envoye:
            
            # Condition A : Trop de lumière dans la pièce (Extinction immédiate !)
            if trop_de_lumiere:
                print(f"\n[SÉCURITÉ TEMPÉRATURE] Température excessive (LDR1:{val_ldr1} | LDR2:{val_ldr2} | Seuil:{seuil_dynamique}).")
                envoyer_code_nec_universel()
                ir_deja_envoye = True
                
            # Condition B : Pas de présence et temps écoulé dépassé
            elif not presence_globale:
                temps_ecoule = time.time() - dernier_mouvement_temps
                if temps_ecoule >= DELAI_INACTIVITE_SEC:
                    print(f"\n[TIMEOUT] Plus de {DELAI_INACTIVITE_SEC}s d'inactivité.")
                    envoyer_code_nec_universel()
                    ir_deja_envoye = True
                    
        # 6. GESTION DE LA LED TÉMOIN PROJECTEUR EN PARALLÈLE          
        if pin_etat_projecteur.value() == 1:
            led_projecteur.value(1)   # Allume la LED du GPIO 1
        else:
            led_projecteur.value(0)   # Éteint la LED du GPIO 1

        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nArrêt du programme.")
finally:
    # Sécurisation complète des composants à la déconnexion
    led_presence.value(0)
    led_projecteur.value(0)
    led_ir.duty_u16(0)
    led_ir_2.duty_u16(0)