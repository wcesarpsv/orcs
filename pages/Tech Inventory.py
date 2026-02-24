import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
from PIL import Image

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Field Inventory Tracker", layout="wide")

DB_PATH = "inventory.db"


# =========================
# DB HELPERS
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS technicians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        email TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT NOT NULL UNIQUE, -- SN lido do barcode/QR
        asset_tag TEXT,                    -- opcional (se você tiver etiqueta interna)
        item_type_id INTEGER NOT NULL,
        description TEXT,
        status TEXT NOT NULL,              -- AVAILABLE / IN_FIELD / INSTALLED / LOST / DAMAGED
        created_at TEXT NOT NULL,
        FOREIGN KEY(item_type_id) REFERENCES item_types(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        technician_id INTEGER NOT NULL,
        request_date TEXT,
        issued_date TEXT,
        installed_date TEXT,
        returned_date TEXT,
        location_place_name TEXT,
        rdl TEXT,
        notes TEXT,
        closed INTEGER NOT NULL DEFAULT 0, -- 0 open, 1 closed
        created_at TEXT NOT NULL,
        FOREIGN KEY(item_id) REFERENCES items(id),
        FOREIGN KEY(technician_id) REFERENCES technicians(id)
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_assignments_open
    ON assignments(closed, technician_id, item_id);
    """)

    conn.commit()
    conn.close()


def qdf(query, params=None):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params or {})
    conn.close()
    return df


def exec_sql(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or {})
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def to_iso(d):
    if d is None:
        return None
    if isinstance(d, (datetime, date)):
        return d.isoformat()
    return str(d)


def today_str():
    return date.today().isoformat()


# =========================
# BARCODE/QR DECODER
# =========================
def decode_barcode_qr(pil_img: Image.Image) -> str | None:
    """
    Lê barcode/QR a partir de uma imagem.
    Requer: pyzbar + libzbar0 (no Streamlit Cloud via packages.txt)
    """
    from pyzbar.pyzbar import decode
    decoded = decode(pil_img.convert("RGB"))
    if not decoded:
        return None
    value = decoded[0].data.decode("utf-8", errors="ignore").strip()
    return value or None


def status_badge(status: str) -> str:
    m = {
        "AVAILABLE": "🟢 AVAILABLE",
        "IN_FIELD": "🟡 IN_FIELD",
        "INSTALLED": "🔵 INSTALLED",
        "LOST": "🔴 LOST",
        "DAMAGED": "🟠 DAMAGED",
    }
    return m.get(status, status)


# =========================
# APP START
# =========================
init_db()

st.title("🧰 Field Inventory Tracker (SST / Carmanah / Tools)")
st.caption("Cadastro de técnicos + itens via camera (barcode/QR) + movimentações (request → issued → installed → returned).")

tabs = st.tabs([
    "📌 Friday Check",
    "👤 Technicians",
    "📦 Item Types",
    "🧾 Items (Scan SN)",
    "🔁 Assignments",
    "📤 Export"
])

# -----------------------------
# TAB: Friday Check
# -----------------------------
with tabs[0]:
    st.subheader("📌 Friday Check (itens em posse / em andamento)")

    techs = qdf("SELECT id, name FROM technicians WHERE active=1 ORDER BY name;")
    items_in_field = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.location_place_name,
            a.rdl,
            a.notes
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id
        WHERE a.closed=0
        ORDER BY t.name, it.name;
    """)

    col1, col2 = st.columns([1, 2])
    with col1:
        selected_tech = st.selectbox(
            "Filtrar por técnico (opcional)",
            options=["(All)"] + (techs["name"].tolist() if len(techs) else [])
        )
    with col2:
        st.write("Baixe o CSV e cole/anexe no e-mail de sexta.")

    if len(items_in_field) == 0:
        st.info("Nenhum assignment aberto. (Nenhum item em posse registrado.)")
    else:
        df = items_in_field.copy()
        if selected_tech != "(All)":
            df = df[df["technician"] == selected_tech].copy()

        def days_since(x):
            if pd.isna(x) or not x:
                return None
            try:
                d = datetime.fromisoformat(str(x)).date()
                return (date.today() - d).days
            except Exception:
                return None

        df["ref_date"] = df["issued_date"].fillna(df["request_date"])
        df["days_since"] = df["ref_date"].apply(days_since)
        df["status"] = df["status"].apply(status_badge)

        show_cols = [
            "technician", "item_type", "serial_number", "asset_tag", "status",
            "request_date", "issued_date", "installed_date", "days_since",
            "location_place_name", "rdl", "notes"
        ]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Baixar CSV do Friday Check",
            data=df[show_cols].to_csv(index=False).encode("utf-8"),
            file_name=f"friday_check_{today_str()}.csv",
            mime="text/csv"
        )

# -----------------------------
# TAB: Technicians
# -----------------------------
with tabs[1]:
    st.subheader("👤 Technicians")

    with st.expander("➕ Add Technician", expanded=True):
        c1, c2, c3 = st.columns([1.2, 1.5, 0.8])
        with c1:
            tech_name = st.text_input("Name", placeholder="Ex: Wagner Veras")
        with c2:
            tech_email = st.text_input("Email (optional)", placeholder="ex: name@company.com")
        with c3:
            tech_active = st.selectbox("Active", [1, 0], format_func=lambda x: "Yes" if x == 1 else "No")

        if st.button("Save Technician", type="primary"):
            if not tech_name.strip():
                st.error("Name é obrigatório.")
            else:
                try:
                    exec_sql(
                        "INSERT INTO technicians(name, email, active, created_at) VALUES (?, ?, ?, ?);",
                        (tech_name.strip(), tech_email.strip() or None, int(tech_active), datetime.utcnow().isoformat())
                    )
                    st.success("Technician cadastrado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Já existe um technician com esse nome.")

    st.divider()
    df = qdf("SELECT id, name, email, active, created_at FROM technicians ORDER BY name;")
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("✏️ Update Technician"):
        if len(df) == 0:
            st.info("Cadastre um technician primeiro.")
        else:
            tech_pick = st.selectbox("Select Technician", df["name"].tolist())
            row = df[df["name"] == tech_pick].iloc[0]
            new_email = st.text_input("Email", value=row["email"] if row["email"] else "")
            new_active = st.selectbox(
                "Active",
                [1, 0],
                index=0 if int(row["active"]) == 1 else 1,
                format_func=lambda x: "Yes" if x == 1 else "No"
            )
            if st.button("Update Technician"):
                exec_sql(
                    "UPDATE technicians SET email=?, active=? WHERE id=?;",
                    (new_email.strip() or None, int(new_active), int(row["id"]))
                )
                st.success("Atualizado.")
                st.rerun()

# -----------------------------
# TAB: Item Types
# -----------------------------
with tabs[2]:
    st.subheader("📦 Item Types (categorias)")

    with st.expander("➕ Add Item Type", expanded=True):
        type_name = st.text_input("Type Name", placeholder='Ex: Carmanah Sign 30" / Printer / Booster / LCD')
        if st.button("Save Item Type", type="primary"):
            if not type_name.strip():
                st.error("Type name é obrigatório.")
            else:
                try:
                    exec_sql("INSERT INTO item_types(name) VALUES (?);", (type_name.strip(),))
                    st.success("Item Type cadastrado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esse Item Type já existe.")

    st.divider()
    df = qdf("SELECT id, name FROM item_types ORDER BY name;")
    st.dataframe(df, use_container_width=True, hide_index=True)

# -----------------------------
# TAB: Items (Scan SN)
# -----------------------------
with tabs[3]:
    st.subheader("🧾 Items (Scan SN via camera)")

    types = qdf("SELECT id, name FROM item_types ORDER BY name;")
    if len(types) == 0:
        st.warning("Cadastre pelo menos 1 Item Type primeiro.")
    else:
        with st.expander("➕ Add Item (scan barcode/QR)", expanded=True):
            st.markdown("#### 📷 Scan Serial Number (Barcode/QR)")

            photo = st.camera_input("Aponte para o barcode/QR do SN e tire a foto")
            scanned_sn = None

            if photo:
                pil_img = Image.open(photo)
                try:
                    scanned_sn = decode_barcode_qr(pil_img)
                    if scanned_sn:
                        st.success(f"✅ Capturado: {scanned_sn}")
                    else:
                        st.warning("Não detectei barcode/QR. Tente aproximar e focar melhor.")
                except Exception as e:
                    st.error("Erro ao ler barcode/QR. Verifique se libzbar0 está instalado (packages.txt).")
                    st.caption(str(e))

            c1, c2, c3 = st.columns([1.3, 1.3, 1.6])
            with c1:
                type_pick = st.selectbox("Item Type", types["name"].tolist())
            with c2:
                status = st.selectbox("Initial Status", ["AVAILABLE", "IN_FIELD", "INSTALLED", "LOST", "DAMAGED"])
            with c3:
                asset_tag = st.text_input("Asset Tag (optional)", placeholder="Ex: ORC-001")

            serial_number = st.text_input("Serial Number (SN)", value=scanned_sn or "", placeholder="Será preenchido pelo scan")
            desc = st.text_input("Description (optional)", placeholder='Ex: "Small Carmanah", "Printer 4x6"')

            if st.button("Save Item", type="primary"):
                if not serial_number.strip():
                    st.error("Serial Number (SN) é obrigatório.")
                else:
                    type_id = int(types[types["name"] == type_pick]["id"].iloc[0])
                    try:
                        exec_sql("""
                            INSERT INTO items(serial_number, asset_tag, item_type_id, description, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (
                            serial_number.strip(),
                            asset_tag.strip() or None,
                            type_id,
                            desc.strip() or None,
                            status,
                            datetime.utcnow().isoformat()
                        ))
                        st.success("Item cadastrado com SN único.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("SN já existe no sistema (duplicado).")

        st.divider()
        df = qdf("""
            SELECT
                i.id,
                it.name AS item_type,
                i.serial_number,
                i.asset_tag,
                i.description,
                i.status,
                i.created_at
            FROM items i
            JOIN item_types it ON it.id = i.item_type_id
            ORDER BY it.name, i.serial_number;
        """)
        if len(df):
            df["status"] = df["status"].apply(status_badge)
        st.dataframe(df, use_container_width=True, hide_index=True)

# -----------------------------
# TAB: Assignments
# -----------------------------
with tabs[4]:
    st.subheader("🔁 Assignments (Request → Issued → Installed → Returned)")

    techs = qdf("SELECT id, name FROM technicians WHERE active=1 ORDER BY name;")
    items = qdf("""
        SELECT
            i.id,
            it.name AS item_type,
            i.serial_number,
            COALESCE(i.asset_tag, '') AS asset_tag,
            COALESCE(i.description, '') AS description,
            i.status
        FROM items i
        JOIN item_types it ON it.id = i.item_type_id
        ORDER BY it.name, i.serial_number;
    """)

    open_assign = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.returned_date,
            a.location_place_name,
            a.rdl,
            a.notes
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id
        WHERE a.closed=0
        ORDER BY a.created_at DESC;
    """)

    st.markdown("### ➕ Create new Assignment (entregar/registrar item com técnico)")
    if len(techs) == 0 or len(items) == 0:
        st.warning("Cadastre technicians e items primeiro.")
    else:
        c1, c2, c3 = st.columns([1.2, 2.2, 1.1])
        with c1:
            tech_pick = st.selectbox("Technician", techs["name"].tolist())
        with c2:
            filter_status = st.selectbox("Mostrar itens", ["AVAILABLE (recommended)", "ALL"])
            items_filtered = items.copy()
            if filter_status.startswith("AVAILABLE"):
                items_filtered = items_filtered[items_filtered["status"] == "AVAILABLE"]

            def item_label(r):
                extra = f" (SN: {r['serial_number']})"
                tag = f" | {r['asset_tag']}" if (r["asset_tag"] or "").strip() else ""
                desc = f" - {r['description']}" if (r["description"] or "").strip() else ""
                return f"{r['item_type']}{extra}{tag}{desc}"

            if len(items_filtered) == 0:
                st.error("Sem itens AVAILABLE. Ajuste status ou feche assignments antigos.")
                item_pick = None
            else:
                items_filtered = items_filtered.copy()
                items_filtered["label"] = items_filtered.apply(item_label, axis=1)
                item_pick = st.selectbox("Item", items_filtered["label"].tolist())

        with c3:
            request_date = st.date_input("Request Date", value=date.today())

        issued_date = st.date_input("Issued Date", value=date.today())
        location_place_name = st.text_input("Place Name (optional)", placeholder="Ex: Shoppers - Markham")
        rdl = st.text_input("RDL (optional)", placeholder="Ex: RDL-1234")
        notes = st.text_area("Notes (optional)", placeholder="Ex: Requested 3 signs + printer; install next week.")

        if st.button("Create Assignment", type="primary", disabled=(item_pick is None)):
            tech_id = int(techs[techs["name"] == tech_pick]["id"].iloc[0])
            item_id = int(items_filtered[items_filtered["label"] == item_pick]["id"].iloc[0])

            # create assignment
            exec_sql("""
                INSERT INTO assignments(
                    item_id, technician_id, request_date, issued_date,
                    location_place_name, rdl, notes, closed, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?);
            """, (
                item_id,
                tech_id,
                to_iso(request_date),
                to_iso(issued_date),
                location_place_name.strip() or None,
                rdl.strip() or None,
                notes.strip() or None,
                datetime.utcnow().isoformat()
            ))

            # update item status
            exec_sql("UPDATE items SET status='IN_FIELD' WHERE id=?;", (item_id,))
            st.success("Assignment criado. Item agora está IN_FIELD.")
            st.rerun()

    st.divider()
    st.markdown("### 📍 Open Assignments")

    if len(open_assign) == 0:
        st.info("Nenhum assignment aberto.")
    else:
        df = open_assign.copy()
        df["status"] = df["status"].apply(status_badge)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### ✏️ Update / Close Assignment")
        pick_id = st.selectbox("Select assignment_id", df["assignment_id"].tolist())
        row = df[df["assignment_id"] == pick_id].iloc[0]

        # Dates
        installed_default = date.today()
        if isinstance(row["installed_date"], str) and row["installed_date"]:
            try:
                installed_default = datetime.fromisoformat(row["installed_date"]).date()
            except Exception:
                pass

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            new_installed = st.date_input("Installed Date (optional)", value=installed_default)
        with c2:
            mark_returned = st.checkbox("Returned (close, item AVAILABLE)")
        with c3:
            mark_lost = st.checkbox("Mark LOST (close)")
        with c4:
            mark_damaged = st.checkbox("Mark DAMAGED (close)")

        new_place = st.text_input("Place Name", value="" if pd.isna(row["location_place_name"]) else str(row["location_place_name"]))
        new_rdl = st.text_input("RDL", value="" if pd.isna(row["rdl"]) else str(row["rdl"]))
        new_notes = st.text_area("Notes", value="" if pd.isna(row["notes"]) else str(row["notes"]))

        if st.button("Save Update"):
            # Update assignment fields
            exec_sql("""
                UPDATE assignments
                SET installed_date=?, location_place_name=?, rdl=?, notes=?
                WHERE id=?;
            """, (to_iso(new_installed), new_place.strip() or None, new_rdl.strip() or None, new_notes.strip() or None, int(pick_id)))

            item_id = int(qdf("SELECT item_id FROM assignments WHERE id=?;", (int(pick_id),))["item_id"].iloc[0])

            if mark_lost:
                exec_sql("UPDATE items SET status='LOST' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Item marcado como LOST e assignment fechado.")
            elif mark_damaged:
                exec_sql("UPDATE items SET status='DAMAGED' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Item marcado como DAMAGED e assignment fechado.")
            elif mark_returned:
                exec_sql("UPDATE items SET status='AVAILABLE' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Assignment fechado. Item voltou para AVAILABLE.")
            else:
                exec_sql("UPDATE items SET status='INSTALLED' WHERE id=?;", (item_id,))
                st.success("Atualizado. Item marcado como INSTALLED (assignment continua aberto).")

            st.rerun()

# -----------------------------
# TAB: Export
# -----------------------------
with tabs[5]:
    st.subheader("📤 Export / Reports")

    df_items = qdf("""
        SELECT
            i.id,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.description,
            i.status,
            i.created_at
        FROM items i
        JOIN item_types it ON it.id = i.item_type_id;
    """)
    df_assign = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.returned_date,
            a.location_place_name,
            a.rdl,
            a.notes,
            a.closed,
            a.created_at
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id;
    """)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Export Items CSV",
            data=df_items.to_csv(index=False).encode("utf-8"),
            file_name=f"items_{today_str()}.csv",
            mime="text/csv"
        )
    with c2:
        st.download_button(
            "⬇️ Export Assignments CSV",
            data=df_assign.to_csv(index=False).encode("utf-8"),
            file_name=f"assignments_{today_str()}.csv",
            mime="text/csv"
        )

    df_show = df_assign.copy()
    if len(df_show):
        df_show["status"] = df_show["status"].apply(status_badge)
    st.dataframe(df_show.sort_values("created_at", ascending=False), use_container_width=True, hide_index=True)
