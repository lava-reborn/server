class lol.gpui.controls.DropList extends lol.gpui.GPUIObject
{
   var _h;
   var _w;
   var _xmouse;
   var _ymouse;
   var curItem;
   var curItem_txt;
   var dispatchEvent;
   var dropListPan;
   var drop_btn;
   static var CHANGED = "CHANGED";
   var _drop = false;
   function DropList()
   {
      super();
      this.dropListPan.listItemLink = "dropListItem";
      this.dropListPan.lineSpace = -3;
      this.dropListPan._visible = false;
      this.doLater("init");
      this.setSize(250,100);
   }
   function init()
   {
      this.drop_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.drop);
      this.dropListPan.addEventListener("click",this,this.selectItem);
   }
   function drop()
   {
      this._drop = !this._drop;
      this.dropListPan._visible = this._drop;
   }
   function setSize(W, H)
   {
      this.dropListPan.setSize(W,H);
      this._w = this.dropListPan._width;
      this._h = H + this.drop_btn._height;
   }
   function addItem(label, data, selected)
   {
      var _loc2_ = this.dropListPan.addItem({label:label,data:data},true);
      if(selected)
      {
         this.curItem = _loc2_;
         this.curItem_txt.text = this.curItem.label;
         _loc2_.toggled = true;
      }
   }
   function removeAll()
   {
      this.dropListPan.clearList();
      delete this.curItem;
      this.curItem_txt.text = "";
   }
   function set label(value)
   {
      this.curItem_txt.text = value;
   }
   function set enabled(value)
   {
      this.drop_btn.enabled = value;
   }
   function selectItem(obj)
   {
      var _loc2_ = lol.gpui.controls.ToggleButton(obj.item);
      _loc2_.toggled = false;
      this.curItem = _loc2_;
      this.curItem.toggled = true;
      this.curItem_txt.text = _loc2_.label;
      this.dispatchEvent({type:lol.gpui.controls.DropList.CHANGED});
      this.drop();
   }
   function onMouseDown()
   {
      var _loc3_ = this._xmouse;
      var _loc2_ = this._ymouse;
      if(_loc3_ < 0 || _loc3_ > this._w || _loc2_ < 0 || _loc2_ > this._h)
      {
         if(this._drop)
         {
            this.drop();
         }
      }
   }
}
