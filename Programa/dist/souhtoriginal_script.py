import sys
import pandas as pd
import psycopg2
from psycopg2 import sql

# ==============================
# 1. Validar argumentos
# ==============================
if len(sys.argv) < 2:
    print("Uso: python souhtoriginal_script.py archivo.xlsx")
    sys.exit(1)

excel_path = sys.argv[1]
print(f"Procesando archivo: {excel_path}")

# ==============================
# 2. Leer el Excel
# ==============================
try:
    df = pd.read_excel(excel_path, dtype=str)  # leer todo como texto
except Exception as e:
    print(f"Error al leer el archivo Excel: {e}")
    sys.exit(1)

expected_columns = [
    "FirstName", "LastName", "DOB", "Provider", "Group", "Time",
    "InitialUpload", "99454 DOS", "Reading Days", "TrainingDate",
    "MRN", "Program"
]
df = df.reindex(columns=expected_columns)
df = df.fillna("")

# ==============================
# 3. Conectar a PostgreSQL
# ==============================
conn = psycopg2.connect(
    host="10.0.1.210",
    dbname="ByB",
    user="postgres",
    password="Q1w2e3r4",
    port="5432"
)
cur = conn.cursor()

# ==============================
# 4. Diccionario para Provider
# ==============================
provider_map = {
    "Dr. Francisco Nascimento": "NASCIMENTO,FRANCISCO",
    "Dr. Bruce Martin": "MARTIN,BRUCE",
    "Dr. Michael Metzger": "METZGER,MICHAEL",
    "Dr. Eric Heller": "HELLER,ERIC",
    "Dr. Gustavo Cardenas": "CARDENAS,GUSTAVO",
    "Dr. Charles Harring": "HARRING,CHARLES",
    "Dr. David Goldgrab": "GOLDGRAB,DAVID",
    "Dr. Andres Ruiz": "RUIZ,ANDRES",
    "Dr. Robert Carida": "CARIDA,ROBERT"
}

# ==============================
# 5. Insertar en SouhtOriginal
# ==============================
insert_original = sql.SQL("""
    INSERT INTO SouhtOriginal (
        firstname, lastname, dob, provider, "group", time,
        initialupload, "99454_dos", reading_days, trainingdate,
        mrn, program
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
""")

# ==============================
# 6. Insertar en SouhtClaims con códigos y facility
# ==============================
insert_procesado = sql.SQL("""
    INSERT INTO SouhtClaims (
        firstname, lastname, dob, provider, "group", time,
        initialupload, "99454_dos", reading_days, trainingdate,
        mrn, program,
        codigo1, codigo2, codigo3, codigo4,
        facility
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
              %s, %s, %s, %s,
              %s)
""")

def asignar_codigos_no_training(time_str, dos_date):
    """Asigna códigos para casos sin training"""
    try:
        time_val = int(time_str)
    except:
        return (None, None, None, None)

    con_fecha = bool(dos_date.strip())

    if 20 <= time_val <= 39:  # VERDE
        return ("99454", "99457", None, None) if con_fecha else ("99457", None, None, None)
    elif 40 <= time_val <= 59:  # AMARILLO
        return ("99454", "99457", "99458", None) if con_fecha else ("99457", "99458", None, None)
    elif time_val >= 60:  # ROJO
        return ("99454", "99457", "99458", "2") if con_fecha else ("99457", "99458", "2", None)
    else:  # time <= 19 → handled outside
        return ("99453", None, None, None)

def asignar_facility(provider_clean):
    """Asigna la facility según el provider"""
    if provider_clean in ["NASCIMENTO,FRANCISCO", "MARTIN,BRUCE"]:
        return "CFM RPM PATIENT"
    elif provider_clean == "HELLER,ERIC":
        return "HHH RPM PATIENT"
    else:
        return "SPCVA RPM PATIENT"

rows_inserted = 0
for _, row in df.iterrows():
    # ==============================
    # Inserción en SouhtOriginal (SIN CAMBIOS)
    # ==============================
    values_original = (
        row["FirstName"], row["LastName"], row["DOB"], row["Provider"],
        row["Group"], row["Time"], row["InitialUpload"], row["99454 DOS"],
        row["Reading Days"], row["TrainingDate"],  # <-- tal cual viene del Excel
        row["MRN"], row["Program"]
    )
    cur.execute(insert_original, values_original)

    # ==============================
    # Procesamiento para SouhtClaims
    # ==============================
    provider_clean = provider_map.get(row["Provider"], row["Provider"])
    trainingdate_excel = row["TrainingDate"].strip()         # lo que trae el Excel
    had_trainingdate = bool(trainingdate_excel)              # bandera
    trainingdate_final = trainingdate_excel or "2025-09-30"  # lo que usamos en claims
    time_val = int(row["Time"]) if row["Time"].isdigit() else 0
    facility = asignar_facility(provider_clean)

    # Caso A: Con TrainingDate en el Excel
    if had_trainingdate:
        # Siempre insertar training
        values_procesado = (
            row["FirstName"], row["LastName"], row["DOB"], provider_clean,
            row["Group"], row["Time"], row["InitialUpload"], row["99454 DOS"],
            row["Reading Days"], trainingdate_final, row["MRN"], row["Program"],
            "99453", None, None, None,
            facility
        )
        cur.execute(insert_procesado, values_procesado)
        rows_inserted += 1

        # Si Time >= 20 → también insertar como no training
        if time_val >= 20:
            codigo1, codigo2, codigo3, codigo4 = asignar_codigos_no_training(
                row["Time"], row["99454 DOS"]
            )
            values_procesado = (
                row["FirstName"], row["LastName"], row["DOB"], provider_clean,
                row["Group"], row["Time"], row["InitialUpload"], row["99454 DOS"],
                row["Reading Days"], trainingdate_final, row["MRN"], row["Program"],
                codigo1, codigo2, codigo3, codigo4,
                facility
            )
            cur.execute(insert_procesado, values_procesado)
            rows_inserted += 1

    # Caso B: Sin TrainingDate en el Excel
    else:
        if time_val <= 19:
            # Training forzado
            values_procesado = (
                row["FirstName"], row["LastName"], row["DOB"], provider_clean,
                row["Group"], row["Time"], row["InitialUpload"], row["99454 DOS"],
                row["Reading Days"], trainingdate_final, row["MRN"], row["Program"],
                "99453", None, None, None,
                facility
            )
            cur.execute(insert_procesado, values_procesado)
            rows_inserted += 1
        else:
            # Solo no training
            codigo1, codigo2, codigo3, codigo4 = asignar_codigos_no_training(
                row["Time"], row["99454 DOS"]
            )
            values_procesado = (
                row["FirstName"], row["LastName"], row["DOB"], provider_clean,
                row["Group"], row["Time"], row["InitialUpload"], row["99454 DOS"],
                row["Reading Days"], trainingdate_final, row["MRN"], row["Program"],
                codigo1, codigo2, codigo3, codigo4,
                facility
            )
            cur.execute(insert_procesado, values_procesado)
            rows_inserted += 1


conn.commit()
cur.close()
conn.close()

print(f"✅ Inserción completada. {rows_inserted} registros subidos a SouhtClaims y SouhtOriginal.")
