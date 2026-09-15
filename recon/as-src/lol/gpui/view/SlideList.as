class lol.gpui.view.SlideList extends lol.gpui.GPUIObject
{
   var _parent;
   var _y;
   var contH;
   var contW;
   var container;
   var dispatchEvent;
   var listArr;
   var listH;
   var listW;
   var mask;
   var onEnterFrame;
   var factor = 3;
   var currentNum = 0;
   function SlideList()
   {
      super();
   }
   function build(arr)
   {
      this.listArr = arr;
      var _loc8_ = 0;
      var _loc2_;
      this.contW = this.listW;
      this.contH = this.listH - arr.length * 16 + 2;
      var _loc4_ = 0;
      var _loc3_;
      var _loc5_;
      var _loc7_;
      while(_loc4_ < arr.length)
      {
         _loc3_ = arr[_loc4_];
         _loc2_ = this.container.attachMovie(_loc3_.linkTitle,_loc3_.linkTitle,this.container.getNextHighestDepth());
         _loc2_._y = Math.round(_loc8_);
         _loc2_.num = _loc4_;
         _loc2_.top = _loc2_._y;
         _loc2_.bottom = Math.round(this.listH - (arr.length - _loc4_) * _loc2_.btn._height);
         _loc5_ = new TextFormat();
         _loc5_.bold = true;
         _loc2_.skill_txt.text = _loc3_.skillNum;
         _loc2_.skill_txt.setTextFormat(_loc5_);
         _loc2_.showSkill(_loc3_.currentSkill);
         _loc2_.bg._width = this.contW;
         _loc2_.bg._height = this.contH;
         _loc2_.openContent(_loc3_.linkContent);
         this.doLater("initListeners",[_loc2_.btn]);
         _loc7_ = "Улучшено на " + _loc3_.currentSkill + "%";
         this.doLater("initHint",[lol.gpui.HintManager["SKILL_BG" + _loc4_],_loc2_.btn,_loc7_]);
         _loc8_ = _loc2_._y + _loc2_.btn._height;
         this.listArr[_loc4_].listBtn = _loc2_;
         _loc4_ = _loc4_ + 1;
      }
      _loc4_ = 1;
      while(_loc4_ < this.listArr.length)
      {
         this.listArr[_loc4_].listBtn._y = this.listArr[_loc4_].listBtn.bottom;
         _loc4_ = _loc4_ + 1;
      }
      return this.listArr;
   }
   function erase()
   {
      for(var _loc2_ in this.container)
      {
         this.container[_loc2_].removeMovieClip();
      }
   }
   function initListeners(mov)
   {
      mov.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectFunc);
      mov.addEventListener("MouseMove",this,this.onMoveSkill);
      mov.onRollOver = function()
      {
         this.dispatchEvent({type:"MouseMove",data:this});
      };
   }
   function onMoveSkill(obj)
   {
      this.dispatchEvent({type:"MouseMove",data:obj.data});
   }
   function initHint(inst, mov, hint)
   {
      lol.core.SceneShifter.hintManager.addHint(inst,mov,hint);
   }
   function kill()
   {
      for(var _loc2_ in this.listArr)
      {
         this.listArr[_loc2_].listBtn.btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.selectFunc);
         this.listArr[_loc2_].listBtn.btn.removeEventListener("MouseMove",this,this.onMoveSkill);
         this.listArr[_loc2_].listBtn.btn.onRollOver = null;
      }
      this.selectFunc.target = null;
      this.selectFunc.func = null;
      this.selectFunc = null;
   }
   function selectFunc(obj)
   {
      var _loc2_ = obj.target._parent.num;
      if(obj.target.toggled)
      {
         this.open(_loc2_);
      }
      else
      {
         obj.target.toggled = false;
      }
   }
   function open(num)
   {
      this.currentNum = num;
      var _loc2_ = 0;
      while(_loc2_ < this.listArr.length)
      {
         if(_loc2_ == num)
         {
            this.listArr[_loc2_].listBtn.btn.toggled = true;
            this.moveTo(this.listArr[_loc2_].listBtn,this.listArr[_loc2_].listBtn.top);
            break;
         }
         this.listArr[_loc2_].listBtn.btn.toggled = false;
         this.moveTo(this.listArr[_loc2_].listBtn,this.listArr[_loc2_].listBtn.top);
         _loc2_ = _loc2_ + 1;
      }
      _loc2_ = this.listArr.length - 1;
      while(_loc2_ >= 0)
      {
         if(_loc2_ == num)
         {
            break;
         }
         this.listArr[_loc2_].listBtn.btn.toggled = false;
         this.moveTo(this.listArr[_loc2_].listBtn,this.listArr[_loc2_].listBtn.bottom);
         _loc2_ = _loc2_ - 1;
      }
   }
   function moveTo(mov, to)
   {
      delete mov.onEnterFrame;
      var path;
      delete mov.onEnterFrame;
      mov.onEnterFrame = function()
      {
         path = this._y - to;
         this._y -= Math.round(path / this._parent._parent.factor);
         this._y = Math.round(this._y);
         if(Math.abs(path) <= 2)
         {
            this._y = Math.round(to);
            delete this.onEnterFrame;
         }
      };
   }
   function setSize(w, h)
   {
      this.listW = w;
      this.listH = h;
      this.mask._width = w;
      this.mask._height = h;
   }
}
