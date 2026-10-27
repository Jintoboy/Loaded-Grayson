# Loaded Grayson

**Loaded Grayson** is an ammunition trade and exchange rebalance mod for [Abiotic Factor](https://store.steampowered.com/app/427410/Abiotic_Factor/) (Unreal Engine 5.4.4).

It rebalances Grayson’s trading inventory with weapon-aligned batch quantities, higher visit stock caps, and circular ammo conversion trades allowing players to trade surplus ammunition of one type for another without infinite arbitrage loops.

---

## Features

- **Actually Useful Quantities**: Raw material trades yield weapon-aligned magazine quantities (20x 9mm pistol ammo, 6x .357 magnum ammo, 15x .308 sniper ammo, 40x 5.56 rifle ammo).
- **Higher Total Stock**: Grayson carries significantly more ammunition per visit (up to 320x 5.56 rifle ammo, 120x 9mm pistol ammo).
- **Circular Ammo Conversion**: Trade any surplus ammo type into the type you actually need through a continuous conversion loop.
- **Zero Arbitrage Guaranteed**: Mathematically tuned exchange fees (30% cycle return) guarantee infinite ammo loops are impossible.
- **High Stock Conversion**: All ammo conversion trades have 99 stock per visit, providing unrestricted exchange utility.
- **Progression-Aligned**: Trades unlock naturally as you explore facility sectors (Manufacturing, Containment Labs, and Hydroplant).
- **Seamless UI**: Exactly 14 shop slots (2 columns of 7) cleanly fill Grayson's trade window with zero UI overflow.

---

## Trade Table

### Material Trades (Raw Materials $\rightarrow$ Ammunition)
| Output Ammunition | Qty | Cost | Stock | Max / Visit | Unlock Flag |
| :--- | :---: | :--- | :---: | :---: | :--- |
| **9mm pistol ammo** | 20 | 1 Robot Oil (`oil_robot`) | 6 | 120 | `Manufacturing_Arrived` |
| **.357 magnum ammo** | 6 | 1 Chains (`chains`) | 4 | 24 | `Manufacturing_Arrived` |
| **12g buckshot** | 2 | 1 Wood Plank (`woodplank`) | 15 | 30 | `Labs_Containment_Entered` |
| **.308 sniper ammo** | 15 | 1 Radioactive Growth (`growth`) | 2 | 30 | `Dams_ReachedCentral` |
| **5.56 rifle ammo** | 40 | 1 Magnetic Alloy (`magalloy`) | 8 | 320 | `Dams_ReachedCentral` |

### Ammo Conversion Trades (Ammunition $\rightarrow$ Ammunition)
| Trade | You Give | You Receive | Stock | Unlock Flag |
| :--- | :--- | :--- | :---: | :--- |
| **9mm to .357** | 30x 9mm pistol ammo | 6x .357 magnum ammo | 99 | `Manufacturing_Arrived` |
| **.357 to 12g** | 16x .357 magnum ammo | 10x 12g buckshot | 99 | `Labs_Containment_Entered` |
| **12g to .308** | 10x 12g buckshot | 5x .308 sniper ammo | 99 | `Dams_ReachedCentral` |
| **.308 to 5.56** | 4x .308 sniper ammo | 40x 5.56 rifle ammo | 99 | `Dams_ReachedCentral` |
| **5.56 to 9mm** | 25x 5.56 rifle ammo | 12x 9mm pistol ammo | 99 | `Dams_ReachedCentral` |

---

## Repository Structure

```text
Loaded-Grayson/
├── .gitignore
├── LICENSE
├── README.md
├── AGENTS.md                          # LLM & developer reference documentation
├── CLAUDE.md
├── Backups/
│   └── trader_MyProject.uasset.bak    # Backup of vanilla Grayson trade asset
├── Tools/
│   ├── ammo_exchange.py               # Trade math calculator & CLI applier
│   ├── patch_uasset_trades.py         # Binary uasset patcher (header & export offsets)
│   └── verify_patch.py                # Asset verification tool
└── MyProjecty8BQn/                    # Unreal Engine Mod Plugin (Upload to Mod.io)
    ├── MyProjecty8BQn.abfmod
    ├── MyProjecty8BQn.uplugin
    ├── TemplateDefs.ini
    ├── Config/Tags/
    ├── Media/
    │   ├── MyProjecty8BQn.png
    │   └── MyProjecty8BQn_Preview.png
    └── Content/
        ├── AbioticModConfig.uasset    # ModPrefix ("NR77R")
        ├── UUGC_Metadata.uasset       # Mod.io cook rules
        └── DataTables/DT_NPC_TraderItems/
            └── trader_MyProject.uasset
```

---

## Tooling & Verification

The scripts in `Tools/` operate directly on the mod assets inside `MyProjecty8BQn/`:

```powershell
# Verify package integrity, export offsets, and all 14 active trades
python Tools/verify_patch.py

# Inspect current exchange rates and arbitrage mathematical proof
python Tools/ammo_exchange.py

# Re-apply exchange trades to trader_MyProject.uasset
python Tools/ammo_exchange.py --apply

# Restore vanilla trades from backup
python Tools/ammo_exchange.py --restore
```

---

## Publishing to Mod.io

1. Open the **Abiotic Factor Mod Editor**.
2. Click the **Mod.io / "Upload Mod"** toolbar button.
3. In the directory picker, select the plugin folder:
   `...\Loaded-Grayson\MyProjecty8BQn`
4. Enter the mod title, summary, and description.
5. Click **Upload Mod File** — the Mod.io cloud cooker will compile and package the mod for Windows.
