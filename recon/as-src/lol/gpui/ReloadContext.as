class lol.gpui.ReloadContext extends lol.gpui.GPUIObject
{
   var _height;
   var _visible;
   var _width;
   var _xmouse;
   var _ymouse;
   var back;
   var back_bottom;
   var back_middle;
   var contextList;
   var equipment;
   var item;
   var name_txt;
   var onMouseMove;
   var removeMovieClip;
   function ReloadContext()
   {
      super();
      var _loc3_ = lol.core.Master.getInstance();
      this.equipment = _loc3_.gamer.equipment;
      this.name_txt.autoSize = true;
      this.name_txt.wordWrap = false;
      this.contextList.listItemLink = "reloadItem";
      this.back_bottom = this.back.back_bottom;
      this.back_middle = this.back.back_middle;
      this.back.onPress = function()
      {
      };
      this.back.useHandCursor = false;
      this.onMouseMove = this.checkOnOver;
      this._visible = false;
   }
   function checkOnOver()
   {
      var _loc4_ = 0;
      var _loc2_ = this._width;
      var _loc5_ = -10;
      var _loc3_ = this._height;
      if(this._xmouse < _loc4_ || this._xmouse > _loc2_)
      {
         this.kill();
      }
      if(this._ymouse < _loc5_ || this._ymouse > _loc3_)
      {
         this.kill();
      }
   }
   function showContextMenu(item)
   {
      var _loc9_ = item.getProp("comp_ammo");
      var _loc6_ = lol.core.Master.getInstance().gamer.equipment.getAmmoExist(item);
      var _loc4_ = 0;
      var _loc3_;
      var _loc2_;
      var _loc5_;
      var _loc7_;
      while(_loc4_ < _loc6_.length)
      {
         _loc3_ = _loc6_[_loc4_];
         _loc2_ = _loc3_.getProp("name");
         _loc5_ = _loc3_.getProp("mod_type");
         _loc2_ = !_loc5_ ? _loc2_ : _loc2_ + " " + _loc5_;
         _loc7_ = new Object();
         _loc7_.label = _loc2_;
         _loc7_.data = _loc3_;
         this.doLater("addItem",[_loc7_]);
         _loc4_ = _loc4_ + 1;
      }
      _loc7_ = new Object();
      _loc7_.data = "unload";
      this.doLater("addItemUnload",[_loc7_]);
      _loc7_.label = "";
      this.doLater("checkSize");
   }
   function addItem(itemObj)
   {
      var _loc3_ = itemObj.label;
      itemObj.label = "";
      var _loc2_ = this.contextList.addItem(itemObj);
      _loc2_.num_txt.textColor = 3947062;
      _loc2_.title_txt.text = _loc3_;
      _loc2_.title_txt.textColor = 3947062;
      _loc2_.addEventListener("click",this,this.select);
      _loc2_.addEventListener("rollOver",this);
      _loc2_.addEventListener("rollOut",this);
      _loc2_.addEventListener("releaseOutside",this);
   }
   function addItemUnload(itemObj)
   {
      var _loc2_ = this.contextList.addItem(itemObj);
      _loc2_.title_txt.text = "Разрядить оружие";
      _loc2_.title_txt.textColor = 3947062;
      _loc2_.addEventListener("click",this,this.select);
      _loc2_.addEventListener("rollOver",this);
      _loc2_.addEventListener("rollOut",this);
      _loc2_.addEventListener("releaseOutside",this);
   }
   function kill()
   {
      delete this.onMouseMove;
      this.removeMovieClip();
   }
   function rollOver(obj)
   {
      obj.target.gotoAndStop(2);
      obj.target.title_txt.textColor = 11446425;
      obj.target.num_txt.textColor = 11446425;
   }
   function rollOut(obj)
   {
      obj.target.gotoAndStop(1);
      obj.target.title_txt.textColor = 3947062;
      obj.target.num_txt.textColor = 3947062;
   }
   function select(obj)
   {
      if(obj.target.data == "unload")
      {
         this.equipment.unloadFireArm(this.item);
      }
      else
      {
         this.equipment.loadFireArm(this.item,obj.target.data);
      }
      this.kill();
   }
   function checkSize()
   {
      var _loc3_ = this.contextList.content._width;
      var _loc2_ = this.contextList.content._height;
      this.contextList.setSize(_loc3_,_loc2_);
      this.back_middle._height = this.contextList._y + _loc2_;
      this.back_bottom._y = this.back_middle._y + this.back_middle._height;
      this._visible = true;
   }
}
