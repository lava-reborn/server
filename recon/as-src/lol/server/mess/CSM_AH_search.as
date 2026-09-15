class lol.server.mess.CSM_AH_search extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_AH_search(target, page, name, cat, subcat, min_lvl, max_lvl, min_a, max_a, min_g, max_g, sort, s_mode)
   {
      super();
      this._name = "ah_search";
      this.addProp("s_mode",s_mode);
      this.addProp("sort",sort);
      this.addProp("max_g",max_g);
      this.addProp("min_g",min_g);
      this.addProp("max_a",max_a);
      this.addProp("min_a",min_a);
      this.addProp("max_lvl",max_lvl);
      this.addProp("min_lvl",min_lvl);
      this.addProp("subcat",subcat);
      this.addProp("cat",cat);
      this.addProp("name",name);
      this.addProp("page",page);
      this.addProp("target",target);
   }
}
