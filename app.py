import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
from google.cloud.firestore_v1.base_query import FieldFilter
import datetime

# Page configuration optimized for a mobile-first layout
st.set_page_config(
    page_title="Telecom Feed Manager",
    page_icon="📡",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize Firestore directly using Streamlit Secrets
@st.cache_resource
def init_firestore():
    """Authenticates with GCP and returns a secure Firestore database instance."""
    try:
        # Pulls the TOML dictionary structure we pasted into Advanced Settings
        key_dict = dict(st.secrets["gcp_service_account"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds, project=key_dict["project_id"])
    except Exception as e:
        st.error(f"Failed to authenticate with Firestore: {e}")
        return None

db = init_firestore()

st.title("📡 Telecom Newsroom")
st.caption("Review, edit, and approve AI-generated drafts for social distribution.")

def get_pending_drafts():
    """Fetches all unprocessed news items ordered by insertion date."""
    if db is None:
        return []
    try:
        docs = (
            db.collection("draft_news")
            .where(filter=FieldFilter("approved", "==", False))
            .order_by("created_at", direction="DESCENDING")
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return []

def approve_item(doc_id):
    """Marks a draft as approved so the publishing module can pick it up."""
    if db:
        db.collection("draft_news").document(doc_id).update({
            "approved": True,
            "approved_at": datetime.datetime.now(datetime.timezone.utc)
        })
        st.toast("🚀 Draft approved and ready for publishing!", icon="✅")

def delete_item(doc_id):
    """Permanently deletes a rejected draft from the collection."""
    if db:
        db.collection("draft_news").document(doc_id).delete()
        st.toast("Removed item from database.", icon="🗑️")

# Fetch current live drafts from Firestore
drafts = get_pending_drafts()

if db is not None:
    if not drafts:
        st.balloons()
        st.success("🎉 No pending drafts! The pipeline is completely clear.")
    else:
        st.metric(label="Pending Review", value=len(drafts))
        st.write("---")

        # Dynamic render loop creating individual UI cards for each draft
        for idx, item in enumerate(drafts):
            # Wrap each news item inside a clean expanding box (first one open by default)
            with st.expander(f"📝 {item.get('title', 'Untitled Article')[:60]}...", expanded=(idx == 0)):
                
                st.markdown(f"**Source URL:** [{item.get('url')}]({item.get('url')})")
                if "created_at" in item and item["created_at"]:
                    # Handle both standard datetime objects and Firestore timestamps securely
                    dt = item["created_at"]
                    if hasattr(dt, "to_datetime"):
                        dt = dt.to_datetime()
                    date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
                    st.caption(f"Captured on: {date_str}")
                
                st.write("---")
                
                # Interactive text field allowing manual edits right before confirmation
                edited_draft = st.text_area(
                    label="Edit X Draft Content",
                    value=item.get("draft_content", ""),
                    height=120,
                    key=f"text_{item['id']}"
                )
                
                # Form layout split columns for control buttons
                col_approve, col_delete = st.columns([1, 1])
                
                with col_approve:
                    if st.button("👍 Approve Post", key=f"app_{item['id']}", use_container_width=True):
                        # Save local text edits to Firestore database context upon confirmation
                        if edited_draft != item.get("draft_content", ""):
                            db.collection("draft_news").document(item["id"]).update({"draft_content": edited_draft})
                        approve_item(item["id"])
                        st.rerun()
                        
                with col_delete:
                    if st.button("🗑️ Delete", key=f"del_{item['id']}", type="secondary", use_container_width=True):
                        delete_item(item["id"])
                        st.rerun()
