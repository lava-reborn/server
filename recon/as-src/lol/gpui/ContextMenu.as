class lol.gpui.ContextMenu extends lol.gpui.GPUIObject
{
   var _xmouse;
   var _ymouse;
   var action_arr;
   var attachMovie;
   var bg_mc;
   var bottom_mc;
   var dispatchEvent;
   var getNextHighestDepth;
   var label_txt;
   var middle_mc;
   var onMouseMove;
   var topY;
   function ContextMenu()
   {
      super();
      this.middle_mc = this.bg_mc.middle_mc;
      this.bottom_mc = this.bg_mc.bottom_mc;
      this.topY = this.middle_mc._y;
      this.action_arr = new Array();
      this.middle_mc._visible = false;
      this.onMouseMove = this._mouseMove;
   }
   function kill()
   {
      for(var _loc2_ in this.action_arr)
      {
         this.action_arr[_loc2_].btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this.action_arr[_loc2_].obj,this.action_arr[_loc2_].function_str);
      }
   }
   function addAction(linkID, obj, function_str, param)
   {
      var _loc5_ = this.middle_mc.duplicateMovieClip(linkID + "middle",this.bg_mc.getNextHighestDepth(),{_x:0,_y:this.topY});
      var _loc3_ = lol.gpui.controls.GPUIButton(this.attachMovie(linkID,linkID,this.getNextHighestDepth(),{_x:7,_y:this.topY}));
      _loc3_.data = {obj:obj,function_str:function_str,param:param};
      this.topY = _loc3_._y + _loc3_._height - 1;
      this.doLater("initBtn",[_loc3_,obj,function_str]);
      this.action_arr.push({btn:_loc3_,obj:obj,function_str:function_str});
      this.bottom_mc._y = this.topY;
   }
   function initBtn(btn, obj, function_str)
   {
      btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectItem);
   }
   function selectItem(obj)
   {
      var _loc2_ = obj.target.data;
      this.dispatchEvent({type:"selectItem",data:_loc2_});
      this.closeContextMenu();
   }
   function closeContextMenu()
   {
      lol.core.SceneShifter.contextMenuManager.closeContextMenu();
   }
   function _mouseMove()
   {
      if(this._xmouse < 0 || this._xmouse > this.bg_mc._width || this._ymouse < 0 || this._ymouse > this.bg_mc._height)
      {
         this.closeContextMenu();
      }
   }
   function set label(value)
   {
      this.label_txt.text = value;
      var _loc2_ = new TextFormat();
      _loc2_.bold = true;
      this.label_txt.setTextFormat(_loc2_);
   }
}
