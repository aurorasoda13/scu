import psycopg2
from flask import Flask, render_template, request, redirect, session, jsonify
from datetime import timedelta, datetime
from flask import send_file
import io
import openpyxl


# Connessione al database (le tue credenziali originali)
connection = psycopg2.connect(
    user="postgres.eyhuidxkqwegdjqfubfp",
    password="ks4grAGXzGAQm5w1",
    host="aws-0-eu-north-1.pooler.supabase.com",
    port=5432,
    dbname="postgres"
)


app = Flask(__name__)
app.secret_key = 'una-chiave-super-segreta'
app.permanent_session_lifetime = timedelta(minutes=30)

@app.route('/')
def index():
    
    session.clear()
    return render_template("index.html")

@app.route('/accedi', methods=['GET', 'POST'])
def accedi():

    if request.method == 'POST':
        nome = request.form.get('nomeutente')
        psw = request.form.get('psw')


        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT nome, id FROM utente WHERE nomeutente = %s AND password=%s", (nome, psw,))
                result = cursor.fetchone()
                if result:
                    session["utente"] = nome
                    session["id_utente"] = result[1]
                    if session.get("id_utente") == "OLP":
                        session["tipo_utente"] = "Don Alessandro"
                    else:
                        session["tipo_utente"] = "Utente"
                    return redirect('/principale')
                else:
                    return render_template("index.html", errore="Credenziali errate")
        except Exception as e:
            print(f"Errore durante l'accesso: {e}")
            return render_template("index.html", errore="Si è verificato un errore")        


@app.route('/principale', methods=['GET']) # Ho rimosso il 'POST' qui, se non è strettamente necessario per filtri specifici non basati su GET
def principale():
    # Verifica se l'utente è autenticato. Se no, reindirizza alla pagina di login.
    if "utente" not in session:
        return redirect('/')

    # Inizializza una lista vuota per i giorni del registro
    giorni = []
    totale_ore_lavorate = 0 # Inizializza per il calcolo delle ore totali

    try:
        with connection.cursor() as cursor:
            tipo_utente = session.get("tipo_utente")
            print(f"Tipo utente in sessione: {tipo_utente}")
            
            # --- Logica per utente "Don Alessandro" ---
            if tipo_utente == "Don Alessandro": # Verifica se l'utente è "Don Alessandro"
                session["utente"] = "Don" # Assicurati che il nome sia sempre corretto nella sessione
                
                # Recupera tutti i dati iniziali per "Don Alessandro"
                # Usa un JOIN tra registro e utente per ottenere nome e cognome
                query_don = "SELECT utente.nome, utente.cognome, registro.id, registro.oraentrata, registro.dataentrata, registro.orauscita, registro.datauscita FROM registro INNER JOIN utente ON registro.idutente = utente.id WHERE flag=FALSE ORDER BY registro.dataentrata DESC, registro.oraentrata DESC"
                cursor.execute(query_don)
                registro_don = cursor.fetchall()

                # Recupera nomi, cognomi e date uniche per i dropdown per il filtro
                cursor.execute("SELECT DISTINCT nome FROM utente ORDER BY nome")
                nomi_unici = [row[0] for row in cursor.fetchall()]
                
                cursor.execute("SELECT DISTINCT cognome FROM utente ORDER BY cognome")
                cognomi_unici = [row[0] for row in cursor.fetchall()]
                
                cursor.execute("SELECT DISTINCT dataentrata FROM registro ORDER BY dataentrata DESC")
                date_uniche = [row[0] for row in cursor.fetchall()]

                return render_template("principale.html", 
                                       nome=session["utente"], # Usa il nome dalla sessione
                                       registro=registro_don, 
                                       nomi_unici=nomi_unici,
                                       cognomi_unici=cognomi_unici,
                                       date_uniche=date_uniche,
                                       tipo_utente=tipo_utente) # Passa il tipo utente al template
            
            # --- Logica per altri utenti ---
            else:
                # Recupera il registro specifico per l'ID utente dalla sessione
                query_utente = "SELECT id, oraentrata, dataentrata, orauscita, datauscita FROM registro WHERE idutente = %s ORDER BY dataentrata DESC, oraentrata DESC"
                cursor.execute(query_utente, (session["id_utente"],))
                registro_utente = cursor.fetchall()

                # Calcola il totale delle ore per l'utente loggato
                for r in registro_utente:
                    # Assicurati che gli indici siano corretti in base alla SELECT
                    # Gli indici del tuo frammento originale erano: r[1] ora_entrata, r[2] data_entrata, r[3] ora_uscita, r[4] data_uscita
                    # La query sopra seleziona id, oraentrata, dataentrata, orauscita, datauscita
                    # Quindi, gli indici saranno: 1 (ora_entrata), 2 (data_entrata), 3 (ora_uscita), 4 (data_uscita)
                    ora_entrata = r[1]
                    data_entrata = r[2]
                    ora_uscita = r[3]
                    data_uscita = r[4]

                    if ora_entrata and ora_uscita and data_entrata and data_uscita:
                        # Combina data e ora per creare oggetti datetime completi
                        entrata = datetime.combine(data_entrata, ora_entrata)
                        uscita = datetime.combine(data_uscita, ora_uscita)
                        
                        # Calcola la differenza e aggiungi al totale
                        diff = uscita - entrata
                        totale_ore_lavorate += diff.total_seconds() / 3600
                
                # Formatta il totale delle ore in un formato leggibile
                ore = int(totale_ore_lavorate)
                minuti = int(round((totale_ore_lavorate - ore) * 60))
                totale_ore_formattato = f"{ore}h {minuti}min"
                
                return render_template("principale.html", 
                                       nome=session["utente"], 
                                       registro=registro_utente, 
                                       totale_ore=totale_ore_formattato,
                                       tipo_utente=tipo_utente) # Passa il tipo utente al template

    except Exception as e:
        print(f"Errore nella route /principale: {e}")
        # In caso di errore, reindirizza alla home con un messaggio generico
        return render_template("index.html", errore="Si è verificato un errore durante il caricamento della pagina principale.")

    # Questo return è un fallback nel caso in cui la logica precedente non portasse a un redirect o render
    # Potrebbe indicare un problema, quindi è meglio reindirizzare a un punto sicuro.
    return redirect('/')


@app.route('/filtra_registro', methods=['GET'])
def filtra_registro():
    # Solo "Don" può filtrare

    # Ottieni i parametri di filtro dalla richiesta
    filtro_nome = request.args.get('nome')
    filtro_cognome = request.args.get('cognome')
    filtro_data = request.args.get('data')

    try:
        with connection.cursor() as cursor:
            # Costruisci la query in modo dinamico
            query = "SELECT utente.nome, utente.cognome, registro.* FROM registro INNER JOIN utente ON registro.idutente = utente.id WHERE flag=FALSE"
            params = []

            if filtro_nome:
                query += " AND utente.nome = %s"
                params.append(filtro_nome)
            
            if filtro_cognome:
                query += " AND utente.cognome = %s"
                params.append(filtro_cognome)

            if filtro_data:
                query += " AND registro.dataentrata = %s"
                params.append(filtro_data)
            
            query += " ORDER BY registro.id DESC"
            
            print(f"Eseguendo query di filtro: {query} con parametri {params}")
            cursor.execute(query, tuple(params))
            registro_filtrato = cursor.fetchall()
            
            # Formatta i risultati per la risposta JSON
            risultati = []
            for entry in registro_filtrato:
                risultati.append({
                    'nome': entry[0],
                    'cognome': entry[1],
                    'ora_entrata': str(entry[3]) if entry[3] else '',
                    'data_entrata': str(entry[4]) if entry[4] else '',
                    'ora_uscita': str(entry[5]) if entry[5] else '',
                    'data_uscita': str(entry[6]) if entry[6] else '',
                    'id': entry[2]
                })

            return jsonify({'success': True, 'registro': risultati})

    except Exception as e:
        print(f"Errore durante il filtraggio: {e}")
        return jsonify({'success': False, 'message': f'Errore del server durante il filtraggio: {e}'}), 500


@app.route('/salva_modifica_registro', methods=['POST'])
def salva_modifica_registro():
    if not session.get("tipo_utente") == "Don Alessandro":
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 403

    data = request.json
    record_id = data.get('id')
    column_name = data.get('column_name')
    new_value = data.get('value')

    print(f"Ricevuti dati: ID={record_id}, Colonna={column_name}, Nuovo valore={new_value}")
    
    allowed_columns = ['oraentrata', 'orauscita', 'dataentrata']
    if column_name not in allowed_columns:
        return jsonify({'success': False, 'message': 'Colonna di modifica non valida'}), 400

    if not column_name or not record_id:
        return jsonify({'success': False, 'message': 'Dati non validi forniti (colonna o ID mancante)'}), 400
    
    converted_value = new_value
    
    try:
        record_id = int(record_id) 
    except ValueError:
        return jsonify({'success': False, 'message': 'ID del record non valido.'}), 400

    try:
        with connection.cursor() as cursor:
            query = f"UPDATE registro SET {column_name} = %s WHERE id = %s"
            print(f"Eseguendo query: {query} con valori {converted_value}, {record_id}")
            cursor.execute(query, (converted_value, record_id))
            connection.commit()
            return jsonify({'success': True, 'message': 'Record aggiornato con successo'})
    except Exception as e:
        connection.rollback()
        print(f"Errore durante l'aggiornamento del registro nel DB: {e}")
        return jsonify({'success': False, 'message': f'Errore del server durante il salvataggio: {e}'}), 500


@app.route('/gestione', methods=['GET'])
def gestione():
    # Solo Don Alessandro può accedere
    if session.get("tipo_utente") != "Don Alessandro":
        return redirect('/')
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, nomeutente AS username, nome, cognome FROM utente where nomeutente != 'Don'AND flag=FALSE ORDER BY id")  # non modificare il nome dell'utente Don Alessandro
        
            utenti = [
                {"id": row[0], "username": row[1], "nome": row[2], "cognome": row[3]}
                for row in cursor.fetchall()
            ]
            print(f"Utenti caricati per gestione: {utenti}")
        return render_template("gestione.html", utenti=utenti)
    except Exception as e:
        print(f"Errore caricamento gestione: {e}")
        return render_template("gestione.html", utenti=[])

# ...existing code...

@app.route('/modifica_utente/<user_id>', methods=['POST'])  # tolto <int:...>
def modifica_utente(user_id):
    # Solo Don Alessandro può modificare
    if session.get("utente") != "Don":
        return redirect('/')
    username = request.form.get('username')
    nome = request.form.get('nome')
    cognome = request.form.get('cognome')
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE utente SET nomeutente=%s, nome=%s, cognome=%s WHERE id=%s",
                (username, nome, cognome, user_id)
            )
            connection.commit()
    except Exception as e:
        connection.rollback()
        print(f"Errore modifica utente: {e}")
    return redirect('/gestione')


# ...existing code...

@app.route('/scarica_excel')
def scarica_excel():
    if session.get("utente") != "Don":
        return redirect('/')

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT utente.nome, utente.cognome, registro.oraentrata, registro.orauscita, registro.dataentrata, registro.datauscita FROM registro INNER JOIN utente ON registro.idutente = utente.id WHERE flag= FALSE ORDER BY registro.id DESC")
            dati = cursor.fetchall()

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Registro"

        # Intestazioni
        ws.append(["Nome", "Cognome", "Ora entrata", "Ora uscita", "Data entrata", "Data uscita"])

        # Dati
        for row in dati:
            ws.append(list(row))

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="registro.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        print(f"Errore durante l'esportazione: {e}")
        return redirect('/')

# ...existing code...

@app.route('/svuota_registro', methods=['POST'])
def svuota_registro():
    if session.get("utente") != "Don":
        return redirect('/')
    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM registro WHERE idutente IN (SELECT id FROM utente WHERE flag=FALSE)")
            connection.commit()
    except Exception as e:
        connection.rollback()
        print(f"Errore durante lo svuotamento del registro: {e}")
    return redirect('/')
# ...existing code...

@app.route('/cambiapsw', methods=['GET', 'POST'])
def cambiapsw():
    if request.method == 'POST':
        vecchia_psw = request.form.get('vecchia_psw')
        nuova_psw = request.form.get('nuova_psw')
        conferma_psw = request.form.get('conferma_psw')

        if nuova_psw != conferma_psw:
            return render_template("cambiapsw.html", errore="Le nuove password non corrispondono")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT nome FROM utente WHERE nomeutente = %s AND password = %s", (session["utente"], vecchia_psw))
                if cursor.fetchone():
                    cursor.execute("UPDATE utente SET password = %s WHERE nomeutente = %s", (nuova_psw, session["utente"]))
                    connection.commit()
                    return redirect('/')
                else:
                    return render_template("cambiapsw.html", errore="Vecchia password errata")
        except Exception as e:
            print(f"Errore durante il cambio password: {e}")
            return render_template("cambiapsw.html", errore="Si è verificato un errore")
    else:
        return render_template("cambiapsw.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=81)