class lol.gpui.APBar extends lol.gpui.GPUIObject
{
   var _parent;
   var apBar;
   var costBar;
   var costCont;
   var createEmptyMovieClip;
   var curAP;
   var curAPCost;
   var doLater;
   var equipment;
   var getNextHighestDepth;
   var maxAP;
   var onEnterFrame;
   var onEnter_mc;
   var otherCost;
   var primItem;
   var barW = 220;
   function APBar()
   {
      super();
      this.doLater("init");
      this.costBar = this.apBar.costBar;
   }
   function init()
   {
      this.equipment = lol.core.Master.getInstance().gamer.equipment;
   }
   function open()
   {
      this.equipment.addEventListener("changePrimary",this);
      this.onEnter_mc.removeMovieClip();
      this.onEnter_mc = this.createEmptyMovieClip("onEnter_mc",this.getNextHighestDepth());
      delete this.onEnter_mc.onEnterFrame;
      this.onEnter_mc.onEnterFrame = function()
      {
         var _loc2_ = - this._parent.back._y;
         this._parent.back._y += _loc2_ / 1.5;
         this._parent.apBar._y += _loc2_ / 1.5;
         if(_loc2_ <= 2)
         {
            this._parent.back._y = 0;
            this._parent.apBar._y = 0;
            delete this.onEnterFrame;
         }
      };
      this.doLater("showAPCost");
   }
   function close()
   {
      this.equipment.removeEventListener("changePrimary",this);
      this.onEnter_mc.removeMovieClip();
      this.onEnter_mc = this.createEmptyMovieClip("onEnter_mc",this.getNextHighestDepth());
      delete this.onEnter_mc.onEnterFrame;
      this.onEnter_mc.onEnterFrame = function()
      {
         var _loc2_ = this._parent.back._y + 24;
         this._parent.back._y -= _loc2_ - _loc2_ / 1.5;
         this._parent.apBar._y -= _loc2_ - _loc2_ / 1.5;
         if(_loc2_ <= 2)
         {
            this._parent.back._y = -24;
            this._parent.apBar._y = -24;
            delete this.onEnterFrame;
         }
      };
   }
   function changePrimary()
   {
      this.primItem.removeEventListener("itemUpdate",this);
      this.primItem = this.equipment.primaryItem;
      this.primItem.addEventListener("itemUpdate",this);
      this.showAPCost();
   }
   function showAP(cap, map)
   {
      this.maxAP = map;
      this.curAP = cap;
      var _loc2_ = 101 - Math.round(cap * 100 / this.maxAP);
      this.apBar.gotoAndStop(_loc2_);
      if(this.curAPCost > 101 - _loc2_)
      {
         this.apBar.line_mc.gotoAndStop(2);
         this.apBar.right_mc.gotoAndStop(2);
      }
      else
      {
         this.apBar.line_mc.gotoAndStop(1);
         this.apBar.right_mc.gotoAndStop(1);
      }
      this.showAPCost();
   }
   function showAPCost()
   {
      this.costCont.removeMovieClip();
      this.costCont = this.apBar.createEmptyMovieClip("costCont",this.getNextHighestDepth());
      var _loc6_;
      if(!this.otherCost)
      {
         _loc6_ = this.equipment.primaryItem.getAP();
      }
      else
      {
         _loc6_ = this.otherCost;
      }
      var _loc7_ = this.equipment.primaryItem.getProp("ammo_count");
      if(_loc7_ == 0)
      {
         _loc6_ = this.equipment.primaryItem.getAP(lol.core.objects.Item.LOAD);
      }
      var _loc5_;
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(_loc6_)
      {
         _loc5_ = !_loc6_ ? 1 : Math.round(_loc6_ * 100 / this.maxAP);
         this.curAPCost = _loc5_;
         _loc5_ = !_loc5_ ? 200 : _loc5_;
         _loc4_ = true;
         _loc2_ = _loc5_;
         while(_loc4_)
         {
            _loc3_ = this.costCont.attachMovie("apCostBar","label" + this.costCont.getNextHighestDepth(),this.costCont.getNextHighestDepth());
            _loc3_._x = Math.round(this.barW * _loc2_ / 100);
            _loc2_ += _loc5_;
            if(_loc2_ > 100)
            {
               _loc4_ = false;
            }
         }
      }
   }
   function itemUpdate(obj)
   {
      this.showAPCost();
   }
}
