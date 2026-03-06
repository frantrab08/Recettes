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

def get_credentials():
    try:
        return st.secrets["LOGIN_USER"], st.secrets["LOGIN_PASSWORD"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv()
        return os.getenv("LOGIN_USER", "pb"), os.getenv("LOGIN_PASSWORD", "pb_recettes!")

# ─── Session state ───────────────────────────────────────────────────
for k, v in {
    "logged_in": False, "page": "home", "recipe": None,
    "confirm_del": False, "n_ings": 1, "n_steps": 0
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── DB helpers ──────────────────────────────────────────────────────
def get_recipes(search="", category_id=None, only_favorites=False):
    q = db.table("recipes").select("*, categories(name)").order("name")
    if category_id:
        q = q.eq("category_id", category_id)
    if only_favorites:
        q = q.eq("is_favorite", True)
    results = q.execute().data
    if search:
        s = search.lower()
        results = [r for r in results if s in r["name"].lower()]
    return results

def get_ingredients(recipe_id):
    return db.table("ingredients").select("*").eq("recipe_id", recipe_id).order("name").execute().data

def get_steps(recipe_id):
    return db.table("steps").select("*").eq("recipe_id", recipe_id).order("step_number").execute().data

def save_steps(recipe_id, steps):
    db.table("steps").delete().eq("recipe_id", recipe_id).execute()
    valid = [s.strip() for s in steps if s.strip()]
    if valid:
        db.table("steps").insert([
            {"recipe_id": recipe_id, "step_number": i + 1, "description": s}
            for i, s in enumerate(valid)
        ]).execute()

def get_tags():
    return db.table("tags").select("*").order("name").execute().data

def get_recipe_tags(recipe_id):
    result = db.table("recipe_tags").select("*, tags(name, id)").eq("recipe_id", recipe_id).execute().data
    return [r["tags"] for r in result if r.get("tags")]

def save_recipe_tags(recipe_id, tag_ids):
    db.table("recipe_tags").delete().eq("recipe_id", recipe_id).execute()
    if tag_ids:
        db.table("recipe_tags").insert(
            [{"recipe_id": recipe_id, "tag_id": tid} for tid in tag_ids]
        ).execute()

def create_tag(name):
    existing = db.table("tags").select("*").eq("name", name).execute().data
    if existing:
        return existing[0]
    return db.table("tags").insert({"name": name}).execute().data[0]

def get_categories():
    return db.table("categories").select("*").order("name").execute().data

def create_category(name):
    return db.table("categories").insert({"name": name}).execute().data[0]

def delete_category(cid):
    db.table("categories").delete().eq("id", cid).execute()

def toggle_favorite(recipe_id, current):
    db.table("recipes").update({"is_favorite": not current}).eq("id", recipe_id).execute()

def create_recipe(name, desc, category_id, prep_time, cook_time, temperature, ings, steps, tag_ids):
    r = db.table("recipes").insert({
        "name": name, "description": desc, "category_id": category_id,
        "prep_time": prep_time, "cook_time": cook_time, "temperature": temperature
    }).execute().data[0]
    if ings:
        db.table("ingredients").insert(
            [{"recipe_id": r["id"], "name": i["name"], "base_quantity": i["qty"]} for i in ings]
        ).execute()
    save_steps(r["id"], steps)
    save_recipe_tags(r["id"], tag_ids)
    return r

def update_recipe(rid, name, desc, category_id, prep_time, cook_time, temperature, ings, steps, tag_ids):
    db.table("recipes").update({
        "name": name, "description": desc, "category_id": category_id,
        "prep_time": prep_time, "cook_time": cook_time, "temperature": temperature
    }).eq("id", rid).execute()
    db.table("ingredients").delete().eq("recipe_id", rid).execute()
    if ings:
        db.table("ingredients").insert(
            [{"recipe_id": rid, "name": i["name"], "base_quantity": i["qty"]} for i in ings]
        ).execute()
    save_steps(rid, steps)
    save_recipe_tags(rid, tag_ids)

def delete_recipe(rid):
    db.table("recipes").delete().eq("id", rid).execute()

# ─── Navigation ──────────────────────────────────────────────────────
def nav(page, recipe=None):
    st.session_state.page = page
    st.session_state.recipe = recipe
    st.session_state.confirm_del = False
    if page == "edit" and recipe:
        st.session_state.n_ings = max(len(get_ingredients(recipe["id"])), 1)
        st.session_state.n_steps = len(get_steps(recipe["id"]))
    elif page == "add":
        st.session_state.n_ings = 1
        st.session_state.n_steps = 0
    st.rerun()

# ════════════════════════════════════════════════════════════════════
# PAGE : LOGIN
# ════════════════════════════════════════════════════════════════════
def page_login():
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.title("🍰 Recettes Pâtissier")
        st.divider()
        with st.form("login"):
            user = st.text_input("Utilisateur")
            pwd = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter", type="primary", use_container_width=True):
                valid_user, valid_pass = get_credentials()
                if user == valid_user and pwd == valid_pass:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Identifiants incorrects.")

# ════════════════════════════════════════════════════════════════════
# PAGE : ACCUEIL
# ════════════════════════════════════════════════════════════════════
def page_home():
    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        st.title("🍰 Mes Recettes")
    with c2:
        if st.button("➕ Nouvelle recette", type="primary", use_container_width=True):
            nav("add")
    with c3:
        if st.button("⚙️ Catégories", use_container_width=True):
            nav("categories")

    # Filtres
    col_search, col_cat, col_tag = st.columns([3, 2, 2])
    with col_search:
        search = st.text_input("🔍 Rechercher", placeholder="Nom ou ingrédient...")
    with col_cat:
        categories = get_categories()
        cat_options = {"Toutes": None} | {c["name"]: c["id"] for c in categories}
        selected_cat = st.selectbox("Catégorie", list(cat_options.keys()))
        selected_cat_id = cat_options[selected_cat]
    with col_tag:
        all_tags = get_tags()
        tag_filter = st.multiselect("🏷️ Tags", [t["name"] for t in all_tags])

    col_fav, _ = st.columns([2, 5])
    with col_fav:
        only_favs = st.checkbox("⭐ Favoris seulement")

    recipes = get_recipes(search, selected_cat_id, only_favs)

    # Recherche par ingrédient si rien trouvé par nom
    if search and not recipes:
        all_r = get_recipes()
        recipes = [r for r in all_r if any(
            search.lower() in i["name"].lower() for i in get_ingredients(r["id"])
        )]
        if recipes:
            st.caption(f"Résultats par ingrédient pour « {search} »")

    # Filtre par tag
    if tag_filter:
        filtered = []
        for r in recipes:
            r_tags = [t["name"] for t in get_recipe_tags(r["id"])]
            if all(t in r_tags for t in tag_filter):
                filtered.append(r)
        recipes = filtered

    if not recipes:
        st.info("Aucune recette trouvée." if (search or tag_filter or only_favs) else "Aucune recette. Clique sur **➕ Nouvelle recette** !")
        return

    st.caption(f"{len(recipes)} recette(s)")
    cols = st.columns(min(len(recipes), 3))
    for i, r in enumerate(recipes):
        ings = get_ingredients(r["id"])
        total = sum(x["base_quantity"] for x in ings)
        cat = r.get("categories") or {}
        r_tags = get_recipe_tags(r["id"])
        with cols[i % 3]:
            with st.container(border=True):
                # Titre + étoile
                tc, sc = st.columns([4, 1])
                with tc:
                    st.subheader(r["name"])
                with sc:
                    star = "⭐" if r.get("is_favorite") else "☆"
                    if st.button(star, key=f"fav_{r['id']}"):
                        toggle_favorite(r["id"], r.get("is_favorite", False))
                        st.rerun()

                if cat.get("name"):
                    st.caption(f"🏷️ {cat['name']}")
                if r_tags:
                    st.caption(" • ".join([f"#{t['name']}" for t in r_tags]))
                if r.get("description"):
                    st.caption(r["description"])
                parts = []
                if r.get("prep_time"):
                    parts.append(f"⏱️ {r['prep_time']} min")
                if r.get("cook_time"):
                    parts.append(f"🔥 {r['cook_time']} min")
                if r.get("temperature"):
                    parts.append(f"🌡️ {r['temperature']}°C")
                if parts:
                    st.caption("  •  ".join(parts))
                m1, m2 = st.columns(2)
                m1.metric("Poids total", f"{total:.0f} g")
                m2.metric("Ingrédients", len(ings))
                if st.button("Voir →", key=f"see_{r['id']}", use_container_width=True):
                    nav("view", r)

# ════════════════════════════════════════════════════════════════════
# PAGE : CATÉGORIES
# ════════════════════════════════════════════════════════════════════
def page_categories():
    c1, c2 = st.columns([4, 1])
    with c1:
        st.title("⚙️ Gérer les catégories")
    with c2:
        if st.button("← Retour", use_container_width=True):
            nav("home")

    with st.form("new_cat"):
        col_in, col_btn = st.columns([3, 1])
        with col_in:
            new_cat = st.text_input("Nouvelle catégorie", placeholder="ex: Viennoiseries")
        with col_btn:
            st.write("")
            if st.form_submit_button("➕ Ajouter", type="primary", use_container_width=True):
                if new_cat.strip():
                    create_category(new_cat.strip())
                    st.rerun()

    st.divider()
    categories = get_categories()
    if not categories:
        st.info("Aucune catégorie pour l'instant.")
        return
    for cat in categories:
        c1, c2 = st.columns([4, 1])
        c1.write(f"🏷️ {cat['name']}")
        with c2:
            if st.button("🗑️", key=f"del_{cat['id']}", use_container_width=True):
                delete_category(cat["id"])
                st.rerun()

# ════════════════════════════════════════════════════════════════════
# PAGE : VISUALISATION RECETTE
# ════════════════════════════════════════════════════════════════════
def page_view():
    recipe = st.session_state.recipe
    if not recipe:
        nav("home")
        return

    data = db.table("recipes").select("*, categories(name)").eq("id", recipe["id"]).execute().data
    if not data:
        nav("home")
        return
    recipe = data[0]

    # Header
    c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
    with c1:
        star = "⭐" if recipe.get("is_favorite") else "☆"
        st.title(f"{star} {recipe['name']}")
    with c2:
        if st.button("⭐ Favori" if not recipe.get("is_favorite") else "★ Retirer", use_container_width=True):
            toggle_favorite(recipe["id"], recipe.get("is_favorite", False))
            st.rerun()
    with c3:
        if st.button("✏️ Modifier", use_container_width=True):
            nav("edit", recipe)
    with c4:
        if st.button("← Accueil", use_container_width=True):
            nav("home")

    # Meta
    cat = recipe.get("categories") or {}
    parts = []
    if cat.get("name"):
        parts.append(f"🏷️ {cat['name']}")
    if recipe.get("prep_time"):
        parts.append(f"⏱️ Préparation : **{recipe['prep_time']} min**")
    if recipe.get("cook_time"):
        parts.append(f"🔥 Cuisson : **{recipe['cook_time']} min**")
    if recipe.get("temperature"):
        parts.append(f"🌡️ **{recipe['temperature']}°C**")
    if parts:
        st.markdown("  •  ".join(parts))

    # Tags
    r_tags = get_recipe_tags(recipe["id"])
    if r_tags:
        st.markdown(" ".join([f"`#{t['name']}`" for t in r_tags]))

    if recipe.get("description"):
        st.markdown(f"*{recipe['description']}*")

    ingredients = get_ingredients(recipe["id"])
    if not ingredients:
        st.warning("Aucun ingrédient dans cette recette.")
        return

    base_total = sum(i["base_quantity"] for i in ingredients)
    st.divider()

    # Ajustement
    st.subheader("⚖️ Ajuster les quantités")
    mode = st.radio("Mode", ["Par poids total", "Par ingrédient"], horizontal=True)
    scale_factor = 1.0

    if mode == "Par poids total":
        col_input, col_info = st.columns([2, 2])
        with col_input:
            new_total = st.number_input("Poids total souhaité (g)", min_value=0.1, value=float(base_total), step=10.0)
            scale_factor = new_total / base_total
        with col_info:
            st.markdown("#### Résultat")
            if abs(scale_factor - 1.0) < 0.001:
                st.info(f"Recette de base : **{base_total:.0f} g**")
            else:
                st.success(f"**{base_total:.0f} g** → **{new_total:.0f} g**  \nMultiplicateur : ×{scale_factor:.3f}")
    else:
        col_sel, col_input, col_info = st.columns([2, 2, 2])
        with col_sel:
            sel = st.selectbox("Ingrédient de référence", [i["name"] for i in ingredients])
            ref = next((i for i in ingredients if i["name"] == sel), None)
        with col_input:
            if ref:
                new_qty = st.number_input("Nouvelle quantité (g)", min_value=0.1, value=float(ref["base_quantity"]), step=1.0)
                scale_factor = new_qty / ref["base_quantity"]
        with col_info:
            if ref:
                st.markdown("#### Résultat")
                if abs(scale_factor - 1.0) < 0.001:
                    st.info(f"Recette de base : **{base_total:.0f} g**")
                else:
                    st.success(
                        f"**{ref['name']}** : {ref['base_quantity']:.0f} g → **{new_qty:.0f} g**  \n"
                        f"Total : **{base_total:.0f} g** → **{base_total * scale_factor:.0f} g**  \n"
                        f"Multiplicateur : ×{scale_factor:.3f}"
                    )

    st.divider()

    # Tableau ingrédients
    st.subheader("📋 Ingrédients")
    adjusted_total = base_total * scale_factor
    is_scaled = abs(scale_factor - 1.0) > 0.001

    h1, h2, h3, h4 = st.columns([3, 2, 2, 1])
    h1.markdown("**Ingrédient**")
    h2.markdown(f"**Base ({base_total:.0f} g)**")
    h3.markdown(f"**Ajusté ({adjusted_total:.0f} g)**" if is_scaled else "**Quantité**")
    h4.markdown("**%**")
    st.divider()

    for ing in ingredients:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
        adjusted = ing["base_quantity"] * scale_factor
        pct = ing["base_quantity"] / base_total * 100
        c1.write(ing["name"])
        c2.write(f"{ing['base_quantity']:.1f} g")
        c3.markdown(f"**{adjusted:.1f} g**" if is_scaled else f"{adjusted:.1f} g")
        c4.write(f"{pct:.1f}%")

    st.divider()
    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
    c1.markdown("**TOTAL**")
    c2.markdown(f"**{base_total:.0f} g**")
    c3.markdown(f"**{adjusted_total:.0f} g**")
    c4.markdown("**100%**")

    # Répartition
    st.divider()
    st.subheader("📊 Répartition")
    for ing in ingredients:
        pct = ing["base_quantity"] / base_total * 100
        col_name, col_bar = st.columns([2, 5])
        col_name.write(ing["name"])
        col_bar.progress(pct / 100, text=f"{pct:.1f}%")

    # Étapes
    steps = get_steps(recipe["id"])
    if steps:
        st.divider()
        st.subheader("📝 Étapes de préparation")
        for step in steps:
            with st.container(border=True):
                st.markdown(f"**Étape {step['step_number']}** — {step['description']}")

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

    existing_ings = get_ingredients(recipe["id"]) if is_edit else []
    existing_steps = get_steps(recipe["id"]) if is_edit else []
    existing_tags = get_recipe_tags(recipe["id"]) if is_edit else []
    categories = get_categories()
    all_tags = get_tags()

    # ── Infos ───────────────────────────────────────────────────────
    st.subheader("Informations")
    name = st.text_input("Nom *", value=recipe["name"] if is_edit else "", placeholder="ex: Tarte aux pommes")
    desc = st.text_area("Description", value=recipe.get("description", "") if is_edit else "", placeholder="Notes, conseils...")

    cat_options = {"(Aucune)": None} | {c["name"]: c["id"] for c in categories}
    current_cat = None
    if is_edit and recipe.get("category_id"):
        current_cat = next((c["name"] for c in categories if c["id"] == recipe["category_id"]), None)
    cat_index = list(cat_options.keys()).index(current_cat) if current_cat in cat_options else 0
    selected_cat = st.selectbox("Catégorie", list(cat_options.keys()), index=cat_index)
    category_id = cat_options[selected_cat]

    # ── Tags ────────────────────────────────────────────────────────
    st.subheader("🏷️ Tags")
    existing_tag_names = [t["name"] for t in existing_tags]
    selected_tag_names = st.multiselect("Tags de la recette", [t["name"] for t in all_tags], default=existing_tag_names)

    col_new_tag, col_add_tag = st.columns([3, 1])
    with col_new_tag:
        new_tag_input = st.text_input("Nouveau tag", placeholder="ex: sans gluten", label_visibility="collapsed")
    with col_add_tag:
        if st.button("➕ Créer tag", use_container_width=True):
            if new_tag_input.strip():
                create_tag(new_tag_input.strip())
                st.rerun()

    # ── Temps & Température ─────────────────────────────────────────
    st.subheader("Temps & Température")
    col1, col2, col3 = st.columns(3)
    with col1:
        prep_time = st.number_input("⏱️ Préparation (min)", min_value=0, value=int(recipe.get("prep_time") or 0) if is_edit else 0, step=5)
    with col2:
        cook_time = st.number_input("🔥 Cuisson (min)", min_value=0, value=int(recipe.get("cook_time") or 0) if is_edit else 0, step=5)
    with col3:
        temperature = st.number_input("🌡️ Température (°C)", min_value=0, value=int(recipe.get("temperature") or 0) if is_edit else 0, step=10)

    # ── Ingrédients ─────────────────────────────────────────────────
    st.divider()
    st.subheader(f"Ingrédients ({st.session_state.n_ings})")
    c_add, c_rem = st.columns(2)
    with c_add:
        if st.button("➕ Ajouter un ingrédient", use_container_width=True):
            st.session_state.n_ings += 1
            st.rerun()
    with c_rem:
        if st.session_state.n_ings > 1 and st.button("➖ Retirer le dernier", use_container_width=True, key="rem_ing"):
            st.session_state.n_ings -= 1
            st.rerun()

    ingredients = []
    for i in range(st.session_state.n_ings):
        ex = existing_ings[i] if i < len(existing_ings) else None
        c1, c2 = st.columns([3, 1])
        with c1:
            n = st.text_input(f"Ingrédient {i + 1}", value=ex["name"] if ex else "", key=f"in_{i}", placeholder="ex: Farine")
        with c2:
            q = st.number_input("Qté (g)", min_value=0.0, value=float(ex["base_quantity"]) if ex else 0.0, step=1.0, key=f"iq_{i}")
        ingredients.append({"name": n.strip(), "qty": q})

    valid_ings = [i for i in ingredients if i["name"]]
    if valid_ings:
        st.info(f"Poids total : **{sum(i['qty'] for i in valid_ings):.0f} g** pour {len(valid_ings)} ingrédient(s)")

    # ── Étapes ──────────────────────────────────────────────────────
    st.divider()
    st.subheader(f"📝 Étapes de préparation ({st.session_state.n_steps})")
    c_add2, c_rem2 = st.columns(2)
    with c_add2:
        if st.button("➕ Ajouter une étape", use_container_width=True):
            st.session_state.n_steps += 1
            st.rerun()
    with c_rem2:
        if st.session_state.n_steps > 0 and st.button("➖ Retirer la dernière", use_container_width=True, key="rem_step"):
            st.session_state.n_steps -= 1
            st.rerun()

    steps = []
    for i in range(st.session_state.n_steps):
        ex_step = existing_steps[i]["description"] if i < len(existing_steps) else ""
        s = st.text_area(f"Étape {i + 1}", value=ex_step, key=f"step_{i}", placeholder=f"Décrire l'étape {i + 1}...")
        steps.append(s)

    # ── Sauvegarder ─────────────────────────────────────────────────
    st.divider()
    c_save, c_del = st.columns([3, 1])
    with c_save:
        if st.button("💾 Sauvegarder", type="primary", use_container_width=True):
            if not name.strip():
                st.error("Le nom est obligatoire.")
            elif not valid_ings:
                st.error("Ajoute au moins un ingrédient.")
            else:
                prep = prep_time if prep_time > 0 else None
                cook = cook_time if cook_time > 0 else None
                temp = temperature if temperature > 0 else None
                tag_ids = [t["id"] for t in all_tags if t["name"] in selected_tag_names]
                if is_edit:
                    update_recipe(recipe["id"], name.strip(), desc, category_id, prep, cook, temp, valid_ings, steps, tag_ids)
                    nav("view", {**recipe, "name": name.strip(), "description": desc})
                else:
                    new_r = create_recipe(name.strip(), desc, category_id, prep, cook, temp, valid_ings, steps, tag_ids)
                    nav("view", new_r)

    if is_edit:
        with c_del:
            if not st.session_state.confirm_del:
                if st.button("🗑️ Supprimer", use_container_width=True):
                    st.session_state.confirm_del = True
                    st.rerun()
            else:
                st.warning("Confirmer ?")
                if st.button("✅ Oui", use_container_width=True):
                    delete_recipe(recipe["id"])
                    nav("home")
                if st.button("❌ Annuler", use_container_width=True):
                    st.session_state.confirm_del = False
                    st.rerun()

# ─── Routeur ─────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    page_login()
else:
    {
        "home":       page_home,
        "view":       page_view,
        "add":        page_form,
        "edit":       page_form,
        "categories": page_categories,
    }.get(st.session_state.page, page_home)()
