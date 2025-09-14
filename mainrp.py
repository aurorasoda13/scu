#!/usr/bin/env python
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import spidev
import time
from RPLCD.i2c import CharLCD
import psycopg2
import datetime

# --- Inizializzazione del lettore RFID ---
reader = SimpleMFRC522()

print("Avvicina la tua carta RFID al lettore...")
print()

# --- Connessione al database (Spostata fuori dal ciclo while) ---
connection = None
try:
    connection = psycopg2.connect(
        user="postgres.eyhuidxkqwegdjqfubfp",
        password="ks4grAGXzGAQm5w1",
        host="aws-0-eu-north-1.pooler.supabase.com",
        port=5432,
        dbname="postgres"
    )
    connection.autocommit = False
    print("Connessione al database stabilita.")
except psycopg2.Error as e:
    print(f"Errore durante la connessione al database: {e}")
    print("Verifica le credenziali, l'indirizzo host e la connettività di rete.")
    exit()
except Exception as e:
    print(f"Errore generico di connessione: {e}")
    exit()

# --- Inizializzazione dell'LCD (Spostata fuori dal ciclo while) ---
lcd = None
try:
    lcd = CharLCD(i2c_expander='PCF8574', address=0x27, port=1, cols=16, rows=2, dotsize=8)
    lcd.clear()
    print("LCD inizializzato.")
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Avvicina la tua")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("carta RFID...")
except Exception as e:
    print(f"Errore durante l'inizializzazione dell'LCD: {e}")
    print("Controlla il cablaggio e l'indirizzo I2C (usa 'sudo i2cdetect -y 1').")


try:
    while True:
        id, text = reader.read()
        
        if isinstance(id, int):
            id_hex_raw = f"{id:08X}"
            id_formatted = " ".join([id_hex_raw[i:i+2] for i in range(0, len(id_hex_raw), 2)])
        else:
            id_formatted = "ID non valido"
            print("Errore: ID letto non è un numero intero.")
            time.sleep(2)
            if lcd:
                lcd.clear()
                lcd.cursor_pos = (0, 0)
                lcd.write_string("Avvicina la tua")
                lcd.cursor_pos = (1, 0)
                lcd.write_string("carta RFID...")
            continue

        print("UID della carta:", id_formatted)
        
        user_name_to_display = "Sconosciuto"
        action_message = "Errore"

        current_timestamp = datetime.datetime.now()
        current_date_str = current_timestamp.strftime('%Y-%m-%d')
        current_time_str = current_timestamp.strftime('%H:%M:%S')

        predicted_exit_time = None
        predicted_exit_time_str = None

        try:
            with connection.cursor() as cursor:
                # 1. Cerca l'utente per nome
                sql_get_user = "SELECT nome FROM utente WHERE id = %s"
                cursor.execute(sql_get_user, (id_formatted,))
                nome_tupla = cursor.fetchone()

                if nome_tupla:
                    user_name_to_display = nome_tupla[0]
                    print("Nome utente trovato:", user_name_to_display)
                else:
                    # Utente non trovato, inseriscilo e usa un nome temporaneo
                    user_name_to_display = "Nuovo Utente"
                    print("Nessun utente trovato con questo ID. Inserimento in corso...")
                    sql_insert_user = "INSERT INTO utente (id, nome) VALUES (%s, %s)"
                    cursor.execute(sql_insert_user, (id_formatted, user_name_to_display))
                    print("Nuovo utente inserito con ID:", id_formatted)
                
            # 2. Gestisci il registro (entrata/uscita)
            with connection.cursor() as cursor:
                sql_last_entry = "SELECT id, oraentrata, orauscita FROM registro WHERE idutente = %s ORDER BY dataentrata DESC, oraentrata DESC LIMIT 1"
                cursor.execute(sql_last_entry, (id_formatted,))
                last_record = cursor.fetchone()

                if last_record and last_record[2] is None:
                    # L'utente sta uscendo
                    print("Registrazione uscita...")
                    action_message = "Arrivederci"
                    sql_update_exit = "UPDATE registro SET orauscita=%s, datauscita=%s WHERE id=%s"
                    cursor.execute(sql_update_exit, (current_time_str, current_date_str, last_record[0]))
                else:
                    # L'utente sta entrando
                    print("Registrazione entrata...")
                    action_message = "Benvenut*"
                    sql_insert_entry = "INSERT INTO registro (oraentrata, dataentrata, idutente) VALUES (%s, %s, %s)"
                    cursor.execute(sql_insert_entry, (current_time_str, current_date_str, id_formatted))

            # Esegui il commit delle transazioni
            connection.commit()
            print("Transazione completata con successo.")
        
        except psycopg2.Error as db_err:
            connection.rollback()
            print(f"Errore del database: {db_err}. Transazione annullata.")
            user_name_to_display = "Errore DB"
            action_message = "Errore"
        except Exception as e:
            connection.rollback()
            print(f"Errore generico durante l'interazione con il database: {e}. Transazione annullata.")
            user_name_to_display = "Errore"
            action_message = "Errore"

        # --- Blocco per il calcolo delle ore già registrate ---
        if action_message == "Benvenut*":
            try:
                with connection.cursor() as cursor:
                    sql_total_time = """
                        SELECT oraentrata, orauscita
                        FROM registro
                        WHERE idutente = %s AND dataentrata = %s AND orauscita IS NOT NULL
                    """
                    cursor.execute(sql_total_time, (id_formatted, current_date_str))
                    sessions = cursor.fetchall()

                total_seconds = 0
                for oraentrata, orauscita in sessions:
                    if oraentrata and orauscita:
                        t1 = datetime.datetime.combine(current_timestamp.date(), oraentrata)
                        t2 = datetime.datetime.combine(current_timestamp.date(), orauscita)
                        total_seconds += int((t2 - t1).total_seconds())

                remaining_seconds = max(0, 18000 - total_seconds)
                predicted_exit_time = current_timestamp + datetime.timedelta(seconds=remaining_seconds)
                predicted_exit_time_str = predicted_exit_time.strftime('%H:%M:%S')
                print(f"Ora di uscita prevista: {predicted_exit_time_str}")
            except Exception as e:
                print(f"Errore durante il calcolo del tempo: {e}")
                predicted_exit_time_str = "N.D."


        # --- Visualizzazione su LCD ---
        if lcd:
            try:
                lcd.clear()
                lcd.cursor_pos = (0, 0)
                
                if action_message == "Benvenut*":
                    lcd.write_string(f"{action_message} {user_name_to_display[:16].ljust(16)}")
                    if predicted_exit_time_str:
                        time.sleep(1)
                        lcd.cursor_pos = (0, 0)
                        lcd.write_string(f"Uscita prevista:")
                        lcd.cursor_pos = (1, 0)
                        lcd.write_string(predicted_exit_time_str[:16].ljust(16))
                elif action_message == "Arrivederci":
                    lcd.write_string(f"{action_message} {user_name_to_display[:16].ljust(16)}")
                else:
                    lcd.write_string(f"{action_message} {user_name_to_display[:16].ljust(16)}")

                time.sleep(3)
                lcd.clear()
                lcd.cursor_pos = (0, 0)
                lcd.write_string("Avvicina la tua")
                lcd.cursor_pos = (1, 0)
                lcd.write_string("carta RFID...")
                print("Messaggio visualizzato su LCD.")
            except Exception as e:
                print(f"Errore durante la scrittura sull'LCD: {e}")
                print("Potrebbe esserci un problema con l'LCD.")
        else:
            print(f"LCD non disponibile. Visualizzazione su console: {action_message} {user_name_to_display}")

        time.sleep(2)
        print("Avvicina la tua carta RFID al lettore...")
        print()

except KeyboardInterrupt:
    print("\nProgramma terminato dall'utente.")
except Exception as e:
    print(f"Si è verificato un errore critico: {e}")
finally:
    if connection:
        connection.close()
        print("Connessione al database chiusa.")
    if lcd:
        # Assicurati di non chiamare lcd.close() se l'LCD non è mai stato inizializzato
        # per evitare un errore se la connessione fallisce.
        if 'lcd' in locals() and lcd is not None:
            lcd.close()
            print("LCD spento e risorse rilasciate.")
    GPIO.cleanup()
    print("Pulizia GPIO completata.")