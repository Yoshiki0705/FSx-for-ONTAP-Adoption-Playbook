"""削除パターン群

各パターンは AWS FSx 管理面では消せない ONTAP オブジェクトを 1 種類ずつ扱う。
共通契約は base.DeletePattern（resolve_dependencies -> delete -> confirm_gone）。
"""
