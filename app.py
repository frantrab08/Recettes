import streamlit as st
from supabase import create_client
import os

# ─── Config ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🍰 Recettes Pâtissier",
    page_icon="🍰",
    layout="wide"
)

# ─── Supabase ────────────────────────────────────────────────────────
@st.cache_resource
def get_db():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
    return create_client(url, key)

db = get_db()

# ─── Session state ───────────────────────────────────────────────────
for k, v in {"page": "home", "recipe": None, "confirm_del": False, "n_ings": 1}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── DB helpers ──────────────────────────────────────────────────────
def get_recipes():
    return db.table("recipes").select("*").order("name").execute().data

def get_ingredients(recipe_id):
    return db.table("ingredients").select("*").eq("recipe_id", recipe_id).order("name").execute().data

def create_recipe(name, desc, ings):
    r = db.table("recipes").insert({"name": name, "description": desc}).execute().data[0]
    if ings:
        db.table("ingredients").insert(
            [{"recipe_id": r["id"], "name": i["name"], "base_quantity": i["qty"]} for i in ings]
        ).execute()
    return r

def update_recipe(rid, name, desc, ings):
    db.table("recipes").update({"name": name, "description": desc}).eq("id", rid).execute()
    db.table("ingredients").delete().eq("recipe_id", rid).execute()
    if ings:
        db.table("ingredients").insert(
            [{"recipe_id": rid, "name": i["name"], "base_quantity": i["qty"]} for i in ings]
        ).execute()

def delete_recipe(rid):
    db.table("recipes").delete().eq("id", rid).execute()

# ─── Navigation ──────────────────────────────────────────────────────
def nav(page, recipe=None):
    st.session_state.page = page
    st.session_state.recipe = recipe
    st.session_state.confirm_del = False
    if page == "edit" and recipe:
        ings = get_ingredients(recipe["id"])
        st.session_state.n_ings = max(len(ings), 1)
    elif page == "add":
        st.session_state.n_ings = 1
    st.rerun()

# ════════════════════════════════════════════════════════════════════
# PAGE : ACCUEIL
# ════════════════════════════════════════════════════════════════════
def page_home():
    c1, c2 = st.columns([4, 1])
    with c1:
        st.title("🍰 Mes Recettes")
    with c2:
        st.write("")
        if st.button("➕ Nouvelle recette", type="primary", use_container_width=True):
            nav("add")

    recipes = get_recipes()
    if not recipes:
        st.info("Aucune recette pour l'instant. Clique sur **➕ Nouvelle recette** pour commencer !")
        return

    cols = st.columns(min(len(recipes), 3))
    for i, r in enumerate(recipes):
        ings = get_ingredients(r["id"])
        total = sum(x["base_quantity"] for x in ings)
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(r["name"])
                if r.get("description"):
                    st.caption(r["description"])
                m1, m2 = st.columns(2)
                m1.metric("Poids total", f"{total:.0f} g")
                m2.metric("Ingrédients", len(ings))
                if st.button("Voir →", key=f"see_{r['id']}", use_container_width=True):
                    nav("view", r)

# ════════════════════════════════════════════════════════════════════
# PAGE : VISUALISATION RECETTE
# ════════════════════════════════════════════════════════════════════
def page_view():
    recipe = st.session_state.recipe
    if not recipe:
        nav("home")
        return

    data = db.table("recipes").select("*").eq("id", recipe["id"]).execute().data
    if not data:
        nav("home")
        return
    recipe = data[0]

    # ── Header ───────────────────────────────────────────────────────
    c1, c2, c3 = st.columns([4, 1, 1])
    with c1:
        st.title(f"🍰 {recipe['name']}")
    with c2:
        if st.button("✏️ Modifier", use_container_width=True):
            nav("edit", recipe)
    with c3:
        if st.button("← Accueil", use_container_width=True):
            nav("home")

    if recipe.get("description"):
        st.markdown(f"*{recipe['description']}*")

    ingredients = get_ingredients(recipe["id"])
    if not ingredients:
        st.warning("Aucun ingrédient dans cette recette.")
        return

    base_total = sum(i["base_quantity"] for i in ingredients)

    st.divider()

    # ── Ajustement ───────────────────────────────────────────────────
    st.subheader("⚖️ Ajuster la recette")

    mode = st.radio(
        "Comment veux-tu ajuster ?",
        ["Par poids total", "Par ingrédient"],
        horizontal=True
    )

    scale_factor = 1.0

    if mode == "Par poids total":
        col_input, col_info = st.columns([2, 2])
        with col_input:
            new_total = st.number_input(
                "Poids total souhaité (g)",
                min_value=0.1,
                value=float(base_total),
                step=10.0
            )
            scale_factor = new_total / base_total
        with col_info:
            st.markdown("#### Résultat")
            if abs(scale_factor - 1.0) < 0.001:
                st.info(f"Quantités de base → **{base_total:.0f} g** au total")
            else:
                st.success(f"**{base_total:.0f} g** → **{new_total:.0f} g**  \nMultiplicateur : ×{scale_factor:.3f}")

    else:  # Par ingrédient
        col_sel, col_input, col_info = st.columns([2, 2, 2])
        with col_sel:
            names = [i["name"] for i in ingredients]
            sel = st.selectbox("Ingrédient de référence", names)
            ref = next((i for i in ingredients if i["name"] == sel), None)
        with col_input:
            if ref:
                new_qty = st.number_input(
                    f"Nouvelle quantité (g)",
                    min_value=0.1,
                    value=float(ref["base_quantity"]),
                    step=1.0
                )
                scale_factor = new_qty / ref["base_quantity"]
        with col_info:
            if ref:
                st.markdown("#### Résultat")
                if abs(scale_factor - 1.0) < 0.001:
                    st.info(f"Quantités de base → **{base_total:.0f} g** au total")
                else:
                    st.success(
                        f"**{ref['name']}** : {ref['base_quantity']:.0f} g → **{new_qty:.0f} g**  \n"
                        f"Total : **{base_total:.0f} g** → **{base_total * scale_factor:.0f} g**  \n"
                        f"Multiplicateur : ×{scale_factor:.3f}"
                    )

    st.divider()

    # ── Tableau des ingrédients ───────────────────────────────────────
    st.subheader("📋 Ingrédients")

    adjusted_total = base_total * scale_factor
    is_scaled = abs(scale_factor - 1.0) > 0.001

    # En-tête du tableau
    h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
    h1.markdown("**Ingrédient**")
    h2.markdown(f"**Base ({base_total:.0f} g)**")
    if is_scaled:
        h3.markdown(f"**Ajusté ({adjusted_total:.0f} g)**")
    else:
        h3.markdown("**Quantité**")
    h4.markdown("**%**")

    st.divider()

    for ing in ingredients:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        adjusted = ing["base_quantity"] * scale_factor
        pct = ing["base_quantity"] / base_total * 100

        c1.write(ing["name"])
        c2.write(f"{ing['base_quantity']:.1f} g")

        if is_scaled:
            # Couleur verte si augmentation, rouge si diminution
            delta = adjusted - ing["base_quantity"]
            c3.markdown(f"**{adjusted:.1f} g**")
        else:
            c3.write(f"{adjusted:.1f} g")

        c4.write(f"{pct:.1f}%")

    # ── Ligne total ───────────────────────────────────────────────────
    st.divider()
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    c1.markdown("**TOTAL**")
    c2.markdown(f"**{base_total:.0f} g**")
    if is_scaled:
        c3.markdown(f"**{adjusted_total:.0f} g**")
    else:
        c3.markdown(f"**{base_total:.0f} g**")
    c4.markdown("**100%**")

    # ── Répartition visuelle ──────────────────────────────────────────
    st.divider()
    st.subheader("📊 Répartition des ingrédients")
    for ing in ingredients:
        pct = ing["base_quantity"] / base_total * 100
        col_name, col_bar = st.columns([2, 5])
        col_name.write(ing["name"])
        col_bar.progress(pct / 100, text=f"{pct:.1f}%")

# ════════════════════════════════════════════════════════════════════
# PAGE : FORMULAIRE AJOUT / MODIFICATION
# ════════════════════════════════════════════════════════════════════
def page_form():
    is_edit = st.session_state.page == "edit"
    recipe = st.session_state.recipe

    st.title("✏️ Modifier la recette" if is_edit else "➕ Nouvelle recette")

    if st.button("← Retour"):
        nav("view", recipe) if is_edit else nav("home")
        return

    existing = get_ingredients(recipe["id"]) if is_edit else []

    st.subheader("Informations")
    name = st.text_input("Nom de la recette *", value=recipe["name"] if is_edit else "", placeholder="ex: Tarte aux pommes")
    desc = st.text_area("Description", value=recipe.get("description", "") if is_edit else "", placeholder="Notes, occasion, conseils...")

    st.divider()
    st.subheader(f"Ingrédients ({st.session_state.n_ings})")

    c_add, c_rem = st.columns(2)
    with c_add:
        if st.button("➕ Ajouter un ingrédient", use_container_width=True):
            st.session_state.n_ings += 1
            st.rerun()
    with c_rem:
        if st.session_state.n_ings > 1 and st.button("➖ Retirer le dernier", use_container_width=True):
            st.session_state.n_ings -= 1
            st.rerun()

    ingredients = []
    for i in range(st.session_state.n_ings):
        ex = existing[i] if i < len(existing) else None
        c1, c2 = st.columns([3, 1])
        with c1:
            n = st.text_input(
                f"Ingrédient {i + 1}",
                value=ex["name"] if ex else "",
                key=f"in_{i}",
                placeholder="ex: Farine"
            )
        with c2:
            q = st.number_input(
                "Quantité (g)",
                min_value=0.0,
                value=float(ex["base_quantity"]) if ex else 0.0,
                step=1.0,
                key=f"iq_{i}"
            )
        ingredients.append({"name": n.strip(), "qty": q})

    valid = [i for i in ingredients if i["name"]]
    if valid:
        total = sum(i["qty"] for i in valid)
        st.info(f"Poids total : **{total:.0f} g** pour {len(valid)} ingrédient(s)")

    st.divider()

    c_save, c_del = st.columns([3, 1])
    with c_save:
        if st.button("💾 Sauvegarder", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Le nom de la recette est obligatoire.")
            elif not valid:
                st.error("Ajoute au moins un ingrédient.")
            else:
                if is_edit:
                    update_recipe(recipe["id"], name.strip(), desc, valid)
                    nav("view", {**recipe, "name": name.strip(), "description": desc})
                else:
                    new_r = create_recipe(name.strip(), desc, valid)
                    nav("view", new_r)

    if is_edit:
        with c_del:
            if not st.session_state.confirm_del:
                if st.button("🗑️ Supprimer", use_container_width=True):
                    st.session_state.confirm_del = True
                    st.rerun()
            else:
                st.warning("Confirmer ?")
                if st.button("✅ Oui, supprimer", use_container_width=True):
                    delete_recipe(recipe["id"])
                    nav("home")
                if st.button("❌ Annuler", use_container_width=True):
                    st.session_state.confirm_del = False
                    st.rerun()

# ─── Routeur ─────────────────────────────────────────────────────────
{
    "home": page_home,
    "view": page_view,
    "add":  page_form,
    "edit": page_form,
}.get(st.session_state.page, page_home)()
