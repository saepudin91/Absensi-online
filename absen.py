import streamlit as st
from datetime import datetime
from PIL import Image
import io
import pandas as pd

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# =================== KONFIGURASI ===================
SHEET_ID = "1yB6e5WhbAg6lQa2RN-U33-67CrQfw2160JEaWpa7lmI"
FOLDER_ID = "1B-unLs4cqQsDvf8N4esPUB_KxvGrr7MK"
SHEET_NAME = "Absensi Online"
# ===================================================

# Autentikasi Google API
credentials = service_account.Credentials.from_service_account_info(
    st.secrets["google"],
    scopes=["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/spreadsheets"]
)

drive_service = build("drive", "v3", credentials=credentials)
sheet_service = build("sheets", "v4", credentials=credentials)

# Inject JS untuk ambil lokasi
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

# Simpan lokasi ke session
if "lat" in location_data and "lon" in location_data:
    st.session_state.latitude = location_data["lat"][0]
    st.session_state.longitude = location_data["lon"][0]

# Judul
st.title("Absensi Online")

tipe_absen = st.radio("Pilih jenis absen:", ["Masuk", "Keluar"])

# Pilihan metode upload
upload_option = st.radio("Pilih metode unggah foto:", ["Kamera", "Upload dari Galeri"])

if upload_option == "Kamera":
    image_file = st.camera_input("Ambil foto sekarang")
else:
    image_file = st.file_uploader("Unggah foto dari galeri", type=["png", "jpg", "jpeg"])

# Proses jika ada foto
if image_file:
    now = datetime.now()
    tanggal = now.strftime("%Y-%m-%d")
    jam = now.strftime("%H:%M:%S")
    nama_file = f"absen_{now.strftime('%Y%m%d_%H%M%S')}.png"

    # Simpan sementara
    image = Image.open(image_file)
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='PNG')
    image_bytes.seek(0)

    # Upload ke Google Drive
    file_metadata = {'name': nama_file, 'parents': [FOLDER_ID]}
    media = MediaIoBaseUpload(image_bytes, mimetype='image/png')
    uploaded_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()
    file_id = uploaded_file.get("id")

    # Buat link Drive
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

    # Tampilkan hasil
    st.success(f"Absen {tipe_absen} berhasil!")
    st.image(image, caption="Foto tersimpan", width=300)
    st.write(f"Link Drive: [Lihat Foto]({file_link})")
    st.write(f"Lokasi: {st.session_state.get('latitude', '')}, {st.session_state.get('longitude', '')}")
