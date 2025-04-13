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

# ===================== AMBIL LOKASI =====================
query_params = st.query_params
if "lat" in query_params and "lon" in query_params:
    st.session_state.latitude = query_params["lat"][0]
    st.session_state.longitude = query_params["lon"][0]

st.components.v1.html("""
<script>
navigator.geolocation.getCurrentPosition(
  function(position) {
    const latitude = position.coords.latitude;
    const longitude = position.coords.longitude;
    window.location.search = "?lat=" + latitude + "&lon=" + longitude;
  },
  function(error) {
    alert("Gagal mengambil lokasi. Coba izinkan akses lokasi di browser.");
  }
)
</script>
""", height=0)

# ===================== TAMPILAN UTAMA =====================
st.title("Absensi Online")

# ===================== FORM ABSENSI =====================
with st.expander("Form Absensi", expanded=True):
    tipe_absen = st.radio("Pilih jenis absen:", ["Masuk", "Keluar"])

    if "show_camera" not in st.session_state:
        st.session_state.show_camera = False

    if not st.session_state.show_camera:
        if st.button("📷 Ambil Foto"):
            st.session_state.show_camera = True

    if st.session_state.show_camera:
        camera_image = st.camera_input("Ambil foto sekarang")

        if camera_image:
            now = datetime.now()
            tanggal = now.strftime("%Y-%m-%d")
            jam = now.strftime("%H:%M:%S")
            nama_file = f"absen_{now.strftime('%Y%m%d_%H%M%S')}.png"

            image = Image.open(camera_image)
            image_bytes = io.BytesIO()
            image.save(image_bytes, format='PNG')
            image_bytes.seek(0)

            # Upload ke Google Drive
            file_metadata = {'name': nama_file, 'parents': [FOLDER_ID]}
            media = MediaIoBaseUpload(image_bytes, mimetype='image/png')
            uploaded_file = drive_service.files().create(
                body=file_metadata, media_body=media, fields='id'
            ).execute()
            file_id = uploaded_file.get("id")
            file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

            # Simpan ke Google Sheet
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

            st.success(f"Absen {tipe_absen} berhasil!")
            st.image(image, caption="Foto tersimpan", width=300)
            st.write(f"[Lihat Foto di Drive]({file_link})")
            st.write(f"Lokasi: {st.session_state.get('latitude', '')}, {st.session_state.get('longitude', '')}")

# ===================== FITUR REKAP =====================
with st.expander("Rekap Data Absensi", expanded=True):
    if st.button("Tampilkan Rekap Data"):
        try:
            data = sheet_service.spreadsheets().values().get(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!A2:G"
            ).execute().get("values", [])

            if not data:
                st.info("Belum ada data absensi.")
            else:
                df = pd.DataFrame(data, columns=["Nama File", "Tanggal", "Masuk", "Keluar", "Link Foto", "Latitude", "Longitude"])
                df["Tanggal"] = pd.to_datetime(df["Tanggal"], errors="coerce").dt.date

                tanggal_list = sorted(df["Tanggal"].dropna().unique())
                selected_date = st.selectbox("Pilih Tanggal", options=["Semua"] + list(map(str, tanggal_list)))

                absen_filter = st.selectbox("Pilih Jenis Absen", ["Semua", "Masuk", "Keluar"])

                if selected_date != "Semua":
                    df = df[df["Tanggal"] == pd.to_datetime(selected_date).date()]
                
                if absen_filter == "Masuk":
                    df = df[df["Masuk"] != ""]
                elif absen_filter == "Keluar":
                    df = df[df["Keluar"] != ""]

                if df.empty:
                    st.info("Tidak ada data yang sesuai dengan filter.")
                else:
                    st.dataframe(df)
                    excel_file = io.BytesIO()
                    df.to_excel(excel_file, index=False)
                    st.download_button("Download Rekap Excel", data=excel_file.getvalue(), file_name="rekap_absensi.xlsx")
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")
