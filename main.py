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
                # Modifiche per utilizzare la nuova query
                cursor.execute("SELECT nome, id FROM utente WHERE nomeutente = %s AND password=%s", (nome, psw,))
                result = cursor.fetchone()
                totale_ore = 0 
                
                if result and result[0] != "Don Alessandro":  #non modificare il nome dell'utente Don Alessandro
                    session["utente"] = nome
                    cursor.execute("select * from registro where idutente = %s", (result[1],))
                    registro = cursor.fetchall()
                    
                    for r in registro:
                        ora_entrata = r[1]
                        data_entrata = r[2]
                        ora_uscita = r[3]
                        data_uscita = r[4]
                        if ora_entrata and ora_uscita and data_entrata and data_uscita:
                            entrata = datetime.combine(data_entrata, ora_entrata)
                            uscita = datetime.combine(data_uscita, ora_uscita)
                            diff = uscita - entrata
                            totale_ore += diff.total_seconds() / 3600
                    ore = int(totale_ore)
                    minuti = int(round((totale_ore - ore) * 60))
                    totale_ore = f"{ore}h {minuti}min"
                    return render_template("principale.html", nome=nome, registro=registro, totale_ore=totale_ore)
                
                elif result and result[0] == "Don Alessandro": #non modificare il nome dell'utente Don Alessandro
                    session["utente"] = nome
                    
                    # Recupera tutti i dati iniziali per Don
                    cursor.execute("select nome, cognome, registro.* from registro inner join utente on registro.idutente = utente.id order by registro.id desc")
                    registro = cursor.fetchall()
                    
                    # Recupera nomi, cognomi e date uniche per i dropdown
                    cursor.execute("SELECT DISTINCT nome FROM utente ORDER BY nome")
                    nomi_unici = [row[0] for row in cursor.fetchall()]
                    
                    cursor.execute("SELECT DISTINCT cognome FROM utente ORDER BY cognome")
                    cognomi_unici = [row[0] for row in cursor.fetchall()]
                    
                    cursor.execute("SELECT DISTINCT dataentrata FROM registro ORDER BY dataentrata DESC")
                    date_uniche = [row[0] for row in cursor.fetchall()]

                    return render_template("principale.html", 
                                            nome=nome, 
                                            registro=registro, 
                                            nomi_unici=nomi_unici,
                                            cognomi_unici=cognomi_unici,
                                            date_uniche=date_uniche)
                
                return render_template("index.html", errore="Credenziali errate")

        except Exception as e:
            print(f"Errore durante l'accesso: {e}")
            return render_template("index.html", errore="Si è verificato un errore")

    else:
        return render_template("index.html")

@app.route('/filtra_registro', methods=['GET'])
def filtra_registro():
    # Solo "Don" può filtrare
    if session.get("utente") != "Don": #non modificare il nome dell'utente Don
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 403

    # Ottieni i parametri di filtro dalla richiesta
    filtro_nome = request.args.get('nome')
    filtro_cognome = request.args.get('cognome')
    filtro_data = request.args.get('data')

    try:
        with connection.cursor() as cursor:
            # Costruisci la query in modo dinamico
            query = "SELECT utente.nome, utente.cognome, registro.* FROM registro INNER JOIN utente ON registro.idutente = utente.id WHERE 1=1"
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
    if not session.get("utente") == "Don":  #non modificare il nome dell'utente Don
        return jsonify({'success': False, 'message': 'Non autorizzato'}), 403

    data = request.json
    record_id = data.get('id')
    column_index = data.get('column_index')
    new_value = data.get('value')

    print(f"Ricevuti dati: ID={record_id}, Colonna={column_index}, Nuovo valore={new_value}")
    
    # Mappa l'indice della colonna HTML al nome della colonna nel database
    # La tabella di Don ha le colonne: Nome(0), Cognome(1), Ora entrata(2), Ora uscita(3), Data entrata(4)
    column_map = {
        2: 'oraentrata',
        3: 'orauscita',
        4: 'dataentrata'
    }
    
    column_name = column_map.get(column_index)

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

# ...existing code...

@app.route('/gestione', methods=['GET'])
def gestione():
    # Solo Don Alessandro può accedere
    if session.get("utente") != "Don":
        return redirect('/')
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, nomeutente AS username, nome, cognome FROM utente where nomeutente != 'Don' ORDER BY id")  # non modificare il nome dell'utente Don Alessandro
            utenti = [
                {"id": row[0], "username": row[1], "nome": row[2], "cognome": row[3]}
                for row in cursor.fetchall()
            ]
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
            cursor.execute("SELECT utente.nome, utente.cognome, registro.oraentrata, registro.orauscita, registro.dataentrata, registro.datauscita FROM registro INNER JOIN utente ON registro.idutente = utente.id ORDER BY registro.id DESC")
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
            cursor.execute("DELETE FROM registro")
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