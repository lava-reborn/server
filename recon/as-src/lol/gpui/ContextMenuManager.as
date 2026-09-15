class lol.gpui.ContextMenuManager
{
   var X;
   var Y;
   var _contextMenu;
   var action_arr;
   var cont_mc;
   var dispatchEvent;
   var label_str;
   var linkID;
   var showFlag = false;
   function ContextMenuManager()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   function openContextMenu(_action_arr, _linkID, _label_str)
   {
      this.action_arr = _action_arr;
      this.linkID = _linkID;
      this.label_str = _label_str;
      this._openContextMenu();
   }
   function _openContextMenu()
   {
      var _loc3_ = lol.core.SceneShifter.linkWindow;
      this.cont_mc.removeMovieClip();
      this.cont_mc = _loc3_.createEmptyMovieClip("contextmenu_mc",_loc3_.getNextHighestDepth());
      this._contextMenu = lol.gpui.ContextMenu(this.cont_mc.attachMovie(this.linkID,this.linkID,this.cont_mc.getNextHighestDepth()));
      this._contextMenu.addEventListener("selectItem",this,this.selectItem);
      this._contextMenu.label = this.label_str;
      var _loc2_ = 0;
      while(_loc2_ < this.action_arr.length)
      {
         this._contextMenu.addAction(this.action_arr[_loc2_].linkID,this.action_arr[_loc2_].obj,this.action_arr[_loc2_].function_str,this.action_arr[_loc2_].data);
         _loc2_ = _loc2_ + 1;
      }
      this.X = this.cont_mc._xmouse - 20;
      this.Y = this.cont_mc._ymouse - 50;
      this._contextMenu._x = this.X;
      this._contextMenu._y = this.Y;
      return this._contextMenu;
   }
   function selectItem(obj)
   {
      this.dispatchEvent(obj);
   }
   function timeOf()
   {
      this.showFlag = true;
   }
   function _mouseUp()
   {
      if(this.showFlag)
      {
         this.showFlag = false;
         this.cont_mc._visible = true;
      }
      else
      {
         this.closeContextMenu();
      }
      delete this._contextMenu.onMouseUp;
   }
   function closeContextMenu()
   {
      lol.core.SceneShifter.contextMenuManager._contextMenu.kill();
      lol.core.SceneShifter.contextMenuManager._contextMenu.removeMovieClip();
   }
}
