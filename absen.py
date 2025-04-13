import streamlit as st
from datetime import datetime
from PIL import Image
import io
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# ============== KONFIGURASI =================
SHEET_ID = "1yB6e5WhbAg6lQa2RN-U33-67CrQfw2160JEaWpa7lmI"
FOLDER_ID = "1B-unLs4cqQsDvf8N4esPUB_KxvGrr7MK"
SHEET_NAME = "Absensi Online"
# ============================================

# Autentikasi Google API
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
)
drive_service = build("drive", "v3", credentials=credentials)
sheet_service = build("sheets", "v4", credentials=credentials)

# Ambil lokasi dari browser
st.components.v1.html("""
<script>
navigator.geolocation.getCurrentPosition(
  function(position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    window.parent.postMessage({latitude: latitude, longitude: longitude}, "*");
  }
)
</script>
""", height=0)

location_data = st.query_params
st.markdown("""
<script>
window.addEventListener('message', (e) => {
    const lat = e.data.latitude;
    const lon = e.data.longitude;
    if(lat && lon){
        window.location.href='/?lat='+lat+'&lon='+lon;
    }
})
</script>
""", unsafe_allow_html=True)

if "lat" in location_data and "lon" in location_data:
    st.session_state.latitude = location_data["lat"][0]
    st.session_state.longitude = location_data["lon"][0]

# ================= UI ====================
st.title("Absensi Online")

menu = st.sidebar.selectbox("Menu", ["Absen", "Upload Manual", "Rekap Data"])

def simpan_absen(image_bytes, nama_file, tipe_absen):
    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    jam = now.strftime("%H:%M:%S")

    # Upload ke Google Drive
    file_metadata = {'name': nama_file, 'parents': [FOLDER_ID]}
    media = MediaIoBaseUpload(image_bytes, mimetype='image/png')
    uploaded_file = drive_service.files().create(
        body=file_metadata, media_body=media, fields='id'
    ).execute()
    file_id = uploaded_file.get("id")
    file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

    # Simpan ke Google Sheets
    row = [
        nama_file,
        tanggal,
        jam if tipe_absen == "Masuk" else "",
        jam if tipe_absen == "Keluar" else "",
        file_link,
        st.session_state.get("latitude", ""),
        st.session_state.get("longitude", "")
    ]
    sheet_service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()
    return file_link

if menu == "Absen":
    tipe_absen = st.radio("Pilih jenis absen:", ["Masuk", "Keluar"])
    if st.button("📷 Ambil Foto"):
        st.session_state.show_camera = True

    if st.session_state.get("show_camera", False):
        camera_image = st.camera_input("Ambil foto sekarang")
        if camera_image:
            image = Image.open(camera_image)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            image_bytes.seek(0)

            nama_file = f"absen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            link = simpan_absen(image_bytes, nama_file, tipe_absen)

            st.success(f"Absen {tipe_absen} berhasil!")
            st.image(image, caption="Foto tersimpan", width=300)
            st.write(f"[Lihat Foto di Drive]({link})")
            st.write(f"Lokasi: {st.session_state.get('latitude', '')}, {st.session_state.get('longitude', '')}")

elif menu == "Upload Manual":
    tipe_absen = st.radio("Jenis absen:", ["Masuk", "Keluar"])
    uploaded_file = st.file_uploader("Upload foto absen (PNG/JPG)", type=["png", "jpg", "jpeg"])
    if uploaded_file:
        image = Image.open(uploaded_file)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format='PNG')
        image_bytes.seek(0)

        nama_file = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        link = simpan_absen(image_bytes, nama_file, tipe_absen)

        st.success(f"Upload dan absen {tipe_absen} berhasil!")
        st.image(image, caption="Foto tersimpan", width=300)
        st.write(f"[Lihat Foto di Drive]({link})")
        st.write(f"Lokasi: {st.session_state.get('latitude', '')}, {st.session_state.get('longitude', '')}")

elif menu == "Rekap Data":
    # Ambil data dari Google Sheets
    data = sheet_service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!A1:G"
    ).execute().get("values", [])

    df = pd.DataFrame(data[1:], columns=data[0])
    df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')

    tanggal_mulai = st.date_input("Tanggal mulai", value=datetime.now())
    tanggal_selesai = st.date_input("Tanggal selesai", value=datetime.now())

    if tanggal_mulai and tanggal_selesai:
        df_filtered = df[(df['Tanggal'] >= pd.to_datetime(tanggal_mulai)) & (df['Tanggal'] <= pd.to_datetime(tanggal_selesai))]
        st.dataframe(df_filtered)

        # Download Excel
        towrite = io.BytesIO()
        df_filtered.to_excel(towrite, index=False, sheet_name="Rekap")
        towrite.seek(0)
        st.download_button("Download Excel", towrite, file_name="Rekap_Absensi.xlsx")
